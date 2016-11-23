from django.db.models import Prefetch
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import detail_route

from munch.core.utils.views import filtered
from munch.core.utils.views import paginated
from munch.core.utils.views import MunchModelViewSetMixin
from munch.core.utils.views import OrganizationOwnedViewSetMixin
from munch.apps.optouts.models import OptOut
from munch.apps.optouts.api.v1.filters import OptOutFilter
from munch.apps.optouts.api.v1.serializers import OptOutSerializer

from ...models import Mail
from ...models import MailBatch
from ...models import MailStatus
from .filters import MailFilter
from .filters import MailStatusFilter
from .serializers import MailSerializer
from .serializers import MailBatchSerializer
from .serializers import MailStatusSerializer


class MailViewSet(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        viewsets.ReadOnlyModelViewSet):
    model = Mail
    serializer_class = MailSerializer
    filter_class = MailFilter

    def get_queryset(self):
        status_qs = MailStatus.objects.order_by(
            'mail', '-creation_date').distinct('mail')
        return super().get_queryset().prefetch_related(
            Prefetch(
                'statuses', queryset=status_qs, to_attr='last_status_cached'))

    @detail_route(methods=['get'])
    def statuses(self, request, pk):
        serializer = MailStatusSerializer(
            self.get_object().statuses.all(),
            many=True, context={'request': request})
        return Response(serializer.data)


class MailBatchViewSet(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        viewsets.ReadOnlyModelViewSet):
    model = MailBatch
    serializer_class = MailBatchSerializer

    @detail_route(methods=['get'])
    @paginated(MailSerializer)
    @filtered(MailFilter)
    def mails(self, request, pk):
        return self.get_object().mails.all()

    @detail_route(methods=['get'])
    def stats(self, request, pk, format=None):
        batch = self.get_object()
        return Response(batch.mk_stats())

    @detail_route(methods=['get'])
    @paginated(MailStatusSerializer)
    @filtered(MailStatusFilter)
    def bounces(self, request, pk):
        batch = self.get_object()
        return MailStatus.objects.filter(
            mail__in=batch.mails.all().only('id'),
            status__in=(MailStatus.BOUNCED, MailStatus.DROPPED))

    @detail_route(methods=['get'])
    @paginated(OptOutSerializer)
    @filtered(OptOutFilter)
    def opt_outs(self, request, pk, format=None):
        identifiers = Mail.objects.filter(
            batch=self.get_object()).values_list('identifier', flat=True)
        return OptOut.objects.filter(identifier__in=identifiers)
