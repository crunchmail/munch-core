import logging
import collections
from urllib.parse import urlparse

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.urls import resolve
from django.urls import Resolver404
from django.urls import get_script_prefix
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import detail_route
from rest_framework import status
from rest_framework_bulk.mixins import BulkCreateModelMixin
from rest_framework_bulk.mixins import BulkDestroyModelMixin
from rest_framework.renderers import JSONRenderer
from rest_framework.renderers import BrowsableAPIRenderer

from munch.core.utils.renderers import HTMLRenderer
from munch.core.utils.renderers import PlainTextRenderer
from munch.core.utils.views import filtered
from munch.core.utils.views import paginated
from munch.core.utils.views import NestedView
from munch.core.utils.views import classproperty
from munch.core.utils.views import MunchModelViewSetMixin
from munch.core.utils.views import OrganizationOwnedViewSetMixin
from munch.apps.optouts.models import OptOut
from munch.apps.optouts.api.v1.filters import OptOutFilter
from munch.apps.optouts.api.v1.serializers import OptOutSerializer

from ...models import Mail
from ...models import Message
from ...models import MailStatus
from ...models import PreviewMail
from ...models import MessageAttachment
from .filters import MailFilter
from .filters import MessageFilter
from .filters import MailStatusFilter
from .serializers import MailSerializer
from .serializers import MessageSerializer
from .serializers import MailStatusSerializer
from .serializers import MailBulkResultSerializer
from .serializers import NestedMailStatusSerializer
from .serializers import MessageAttachmentSerializer
from .serializers import PreviewRecipientsSerializer
from .permissions import MailPermission
from .permissions import AttachmentPermission
from .permissions import PreviewMailPermission

log = logging.getLogger(__name__)


class MessageViewSet(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        viewsets.ModelViewSet):
    model = Message
    serializer_class = MessageSerializer
    filter_class = MessageFilter

    def _is_message_editable_state(self, pk):
        status = get_object_or_404(Message, pk=pk).status
        return not (status in (Message.SENDING, Message.SENT))

    def destroy(self, request, pk=None):
        if self._is_message_editable_state(pk):
            return super().destroy(request, pk)
        else:
            return Response({'error': 'Cannot delete a sending campaign'},
                            status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request, pk=None, *args, **kwargs):
        if self._is_message_editable_state(pk):
            return super().update(request, pk, *args, **kwargs)
        else:
            return Response({'error': 'Cannot update a sending campaign'},
                            status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, pk=None):
        if self._is_message_editable_state(pk):
            return super().partial_update(request, pk)
        else:
            return Response({'error': 'Cannot update a sending campaign'},
                            status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @detail_route(methods=['get'])
    @paginated(MessageAttachmentSerializer)
    def attachments(self, request, pk):
        message = self.get_object()
        return message.attachments.all()

    @detail_route(methods=['get'])
    @paginated(MailStatusSerializer)
    @filtered(MailStatusFilter)
    def bounces(self, request, pk):
        message = self.get_object()
        return MailStatus.objects.filter(
            status__in=(MailStatus.BOUNCED, MailStatus.DROPPED),
            mail__message=message)

    @detail_route(methods=['get'])
    @paginated(MailSerializer)
    @filtered(MailFilter)
    def recipients(self, request, pk):
        return self.get_object().mails.all()

    @detail_route(methods=['get'])
    @paginated(OptOutSerializer)
    @filtered(OptOutFilter)
    def opt_outs(self, request, pk, format=None):
        identifiers = Mail.objects.filter(
            message=self.get_object()).values_list('identifier', flat=True)
        return OptOut.objects.filter(identifier__in=identifiers)

    @detail_route(
        methods=['get'], renderer_classes=(
            JSONRenderer, BrowsableAPIRenderer,
            HTMLRenderer, PlainTextRenderer))
    def preview(self, request, pk=None, format=None):
        msg = self.get_object()
        if format == 'txt':
            resp = msg.mk_plaintext()
        elif format == 'html':
            resp = msg.mk_html()
        else:
            resp = collections.OrderedDict((
                ('recipients', msg.willsend_addresses()),
                ('excluded_recipients', msg.willnotsend_addresses()),
                ('spam_score', msg.spam_score),
                ('is_spam', msg.is_spam),
                ('html', msg.mk_html()),
                ('plaintext', msg.mk_plaintext()),
            ))
        return Response(resp)

    @detail_route(methods=['get'])
    def stats(self, request, pk, format=None):
        message = self.get_object()
        return Response(message.mk_stats())


class PreviewSendMessageView(NestedView):
    """ Sends a preview email to some recipients

    Not comptabilized in stats.
    """
    serializer_class = PreviewRecipientsSerializer
    parent_model = Message
    permission_classes = [PreviewMailPermission]

    def post(self, request, msg_pk, format=None):
        m = self.get_parent_object(msg_pk)

        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            addrs = serializer.validated_data['recipient']
            mails = [
                PreviewMail.objects.create(
                    message=m, recipient=i) for i in addrs]
            [PreviewMail.send_preview(mail.pk) for mail in mails]
            return Response('Preview mail sent to {}'.format(addrs))
        else:
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MailViewSet(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        BulkCreateModelMixin,
        BulkDestroyModelMixin,
        viewsets.ModelViewSet):
    model = Mail
    serializer_class = MailSerializer
    filter_class = MailFilter
    permission_classes = [MailPermission]

    def get_queryset(self, with_statuses=True):
        qs = super().get_queryset()
        if with_statuses:
            status_qs = MailStatus.objects.order_by(
                'mail', '-creation_date').distinct('mail')
            qs = qs.prefetch_related(Prefetch(
                'statuses', queryset=status_qs, to_attr='last_status_cached'))
        return qs

    def bulk_destroy(self, request, *args, **kwargs):
        if not request.data:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        qs = self.get_queryset()
        ids = []

        for url in request.data:
            try:
                http_prefix = url.startswith(('http:', 'https:'))
            except AttributeError:
                return Response(status=status.HTTP_400_BAD_REQUEST)

            if http_prefix:
                # If needed convert absolute URLs to relative path
                url = urlparse(url).path
                prefix = get_script_prefix()
                if url.startswith(prefix):
                    url = '/' + url[len(prefix):]

            try:
                match = resolve(url)
            except Resolver404:
                return Response(status=status.HTTP_400_BAD_REQUEST)

            try:
                pk = int(match.kwargs.get('pk'))
            except (ValueError, TypeError):
                return Response(status=status.HTTP_400_BAD_REQUEST)

            ids.append(pk)

        if not ids:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        qs.filter(id__in=ids).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    def create(self, request, *args, **kwargs):
        bulk = isinstance(request.data, list)

        must_lock = False
        message_id = None

        if request.data:
            if bulk:
                if request.data and isinstance(request.data[0], dict):
                    message_id = request.data[0].get('message')
            else:
                message_id = request.data.get('message')

            if message_id:
                must_lock = True

        if must_lock:
            try:
                match = resolve(urlparse(message_id).path)
                message_id = match.kwargs.get('pk')
            except Resolver404:
                message_id = None

            if message_id:
                lock_name = 'mail-lock:{}'.format(message_id)
                log.debug('[{}] Waiting for lock ({})...'.format(
                    match.view_name, lock_name))
                lock = cache.lock(lock_name, timeout=15)
                lock.acquire()

        try:
            if not bulk:
                return super(BulkCreateModelMixin, self).create(
                    request, *args, **kwargs)
            else:

                serializer = self.get_serializer(data=request.data, many=True)
                serializer.build_detailed_response()

                recipients = []
                for item in serializer._validated_data:
                    recipients.append(item['recipient'])

                self.perform_bulk_create(serializer)

                mails = self.get_queryset(
                    with_statuses=False).filter(
                        recipient__in=recipients).filter(
                            message=message_id)
                mails_serializer = MailBulkResultSerializer(
                    mails, many=True, context={'request': request})

                detailed_response = serializer._detailed_response
                detailed_response['results'] = mails_serializer.data

                try:
                    lock.release()
                except:
                    pass

                return Response(
                    data=detailed_response,
                    status=status.HTTP_201_CREATED)
        except Exception:
            try:
                lock.release()
            except:
                pass

            raise

    @detail_route(methods=['get'])
    @paginated(NestedMailStatusSerializer)
    @filtered(MailStatusFilter)
    def status_log(self, request, pk):
        mail = self.get_object()
        return mail.statuses.order_by('creation_date')


class MailOptOutView(NestedView):
    """ OptOuts the selected mail, via API
    """
    parent_model = Mail

    def post(self, request, mail_pk, format=None):
        mail = self.get_parent_object(mail_pk)
        OptOut.objects.create(
            author=mail.message.author,
            category=mail.message.category,
            identifier=mail.identifier,
            address=mail.recipient,
            origin=OptOut.BY_API)
        return Response()


class BouncesViewSet(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        viewsets.ModelViewSet):
    model = MailStatus
    serializer_class = MailStatusSerializer
    filter_class = MailStatusFilter

    def get_queryset(self):
        return super().get_queryset().bounces()


class MessageAttachmentViewset(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        viewsets.ModelViewSet):
    model = MessageAttachment
    serializer_class = MessageAttachmentSerializer

    @classproperty
    @classmethod
    def permission_classes(cls):
        return cls.mk_permission_classes([AttachmentPermission])

    def _get_file_response(self, attachment):
        from django.http import HttpResponse
        filename, content, mimetype = attachment.to_email_attachment()
        response = HttpResponse(content)
        response['Content-Type'] = mimetype
        response['Content-Length'] = attachment.size
        return (response, filename)

    @detail_route(methods=['get'])
    def download(self, request, pk, format=None):
        response, filename = self._get_file_response(self.get_object())
        response['Content-Disposition'] = 'attachment; filename={}'.format(
            filename)
        return response

    @detail_route(methods=['get'])
    def content(self, request, pk, format=None):
        response, filename = self._get_file_response(self.get_object())
        response['Content-Disposition'] = 'inline; filename={}'.format(
            filename)
        return response
