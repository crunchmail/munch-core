from django.db import transaction
from django.db.models import Prefetch
from django.db.utils import IntegrityError
from rest_framework import status
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.decorators import list_route
from rest_framework.decorators import detail_route
from rest_framework_bulk.mixins import BulkCreateModelMixin

from munch.core.utils.views import NestedView
from munch.core.utils.views import NestedViewMixin
from munch.core.utils.views import MunchModelViewSetMixin
from munch.core.utils.views import OrganizationOwnedViewSetMixin

from ...models import PROP_TYPES
from ...models import Contact
from ...models import ContactList
from ...models import ContactQueue
from ...models import ContactListPolicy
from .serializers import ContactSerializer
from .serializers import ContactListSerializer
from .serializers import NestedContactSerializer
from .serializers import ContactListListSerializer
from .permissions import ContactListMergePermission
from .serializers import QueuePolicySerializer
from .serializers import ContactQueueSerializer
from .serializers import ContactQueueDetailSerializer


class ContactListViewSet(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        viewsets.ModelViewSet):
    model = ContactList
    serializer_class = ContactListSerializer
    queryset = ContactList.objects.all()


class ContactViewSet(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        BulkCreateModelMixin,
        viewsets.ModelViewSet):
    model = Contact
    serializer_class = ContactSerializer

    def get_queryset(self):
        return Contact.objects.all().prefetch_related(Prefetch(
            'contact_list',
            queryset=ContactList.objects.all().only('contact_fields')))

    def create(self, request, *args, **kwargs):
        bulk = isinstance(request.data, list)

        if not bulk:
            return super(BulkCreateModelMixin, self).create(
                request, *args, **kwargs)

        else:

            serializer = self.get_serializer(data=request.data, many=True)
            has_errors = serializer.is_partly_invalid()

            if not has_errors:
                self.perform_bulk_create(serializer)
                return Response(status=status.HTTP_201_CREATED)
            else:
                return Response(
                    data=serializer._partial_errors,
                    status=status.HTTP_400_BAD_REQUEST)


class ContactListContacts(ContactViewSet, NestedViewMixin):
    """Access and import *contacts* to a given *list*.

    # CSV import

    - set correct content-type : `Content-type: text/csv; charset=utf-8`
    - your CSV first row should be header (field names)


    `address` field will go to `address` field on contact resource, all the
       other fields will go in the *properties* dict.

    If your CSV file contains more fields than you need, you can include
    only some with `fields` url querystring, (i.e: `?fields=[foo,bar]`
    to import only `foo` and `bar` fields), others will be discarded.
    """
    serializer_class = NestedContactSerializer
    parent_model = ContactList

    def get_parent_object(self, pk=None):
        if pk is None:
            pk = self.kwargs['contact_list_pk']
        return super().get_parent_object(pk)

    def get_queryset(self):
        contact_list = self.get_parent_object()
        return contact_list.contacts.filter(contact_list=contact_list)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['kwargs'] = self.kwargs
        return context


class ContactListMergeView(NestedView):
    """ Merge several contact lists into one

    The *master list* that will receive the others contents is the
    one pointed by URL.

    Request payload is an array of *lists* URL to be merged in
    the *master list*.

    *e.g:*

        POST /v1/contact/lists/1/merge/
        ['/v1/contacts/lists/2/', '/v1/contacts/lists/3/']

    The contact lists in arguments will then be deleted.

    """
    parent_model = ContactList
    permission_classes = [ContactListMergePermission]

    def post(self, request, contact_list_pk):
        master_list = self.get_parent_object(contact_list_pk)

        serializer = ContactListListSerializer(
            data={'contact_lists': request.data},
            master_list=master_list,
            context={'request': request},)

        if serializer.is_valid():
            included_lists = serializer.validated_data['contact_lists']
            # Optimistic merge: we try first and de-duplicate if the re is any
            # error on update
            try:
                with transaction.atomic():
                    Contact.objects.filter(contact_list__in=included_lists)\
                                   .update(contact_list=master_list)
            except IntegrityError:
                # get the doubles
                double_addrs = (
                    set(Contact.objects.filter(
                        contact_list__in=included_lists).values_list(
                            'address', flat=True)) &
                    set(Contact.objects.filter(contact_list=master_list)
                        .values_list('address', flat=True))
                )
                Contact.objects.filter(contact_list__in=included_lists)\
                               .exclude(address__in=double_addrs)\
                               .update(contact_list=master_list)

            for i in included_lists:
                i.delete()
            master_list_serializer = ContactListSerializer(
                master_list, context={'request': request})

            return Response(
                data=master_list_serializer.data, status=status.HTTP_200_OK)

        else:
            errors = {api_settings.NON_FIELD_ERRORS_KEY: []}

            # put every error in non_field_errors
            if api_settings.NON_FIELD_ERRORS_KEY not in errors:
                errors[api_settings.NON_FIELD_ERRORS_KEY] = []
            for k, v in serializer.errors.items():
                errors[api_settings.NON_FIELD_ERRORS_KEY] += v

            return Response(data=errors, status=status.HTTP_400_BAD_REQUEST)


class ContactQueueViewSet(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        viewsets.ModelViewSet):
    model = ContactQueue
    serializer_class = ContactQueueSerializer
    queryset = ContactQueue.objects.all()

    @detail_route(methods=['post', 'get'])
    def consume(self, request, pk):
        queue = self.get_object()
        if 'status' in request.GET:
            queue.contacts = queue.consume(status=request.GET['status'])
        else:
            queue.contacts = queue.consume()

        serializer = ContactQueueDetailSerializer(
            queue, context={'request': self.request})
        return Response(serializer.data)

    @list_route(methods=['get'])
    def fields(self, request):
        return Response(PROP_TYPES)


class ContactListPolicyViewSet(MunchModelViewSetMixin, viewsets.ModelViewSet):
    model = ContactListPolicy
    serializer_class = QueuePolicySerializer
    queryset = ContactListPolicy.objects.all()
