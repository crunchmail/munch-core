from rest_framework import viewsets
from rest_framework.response import Response

from munch.core.utils.views import NestedView
from munch.core.utils.views import MunchModelViewSetMixin
from munch.core.utils.views import OrganizationOwnedViewSetMixin

from ...models import SendingDomain
from .filters import SendingDomainFilter
from .serializers import SendingDomainSerializer


class SendingDomainViewSet(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        viewsets.ModelViewSet):
    model = SendingDomain
    serializer_class = SendingDomainSerializer
    filter_class = SendingDomainFilter

    def get_queryset(self):
        qs = super().get_queryset() | SendingDomain.objects.filter(
            alt_organizations__in=[self.request.user.organization])
        return qs.distinct()


class SendingDomainRevalidateView(NestedView):
    """ Allows to revalidate a domain

    Outputs the revalidation response, ex:
    `{"dkim_status":"ko"}`
    """
    parent_model = SendingDomain

    def post(self, request, pk):
        from ...tasks import validate_sending_domain_field

        domain = SendingDomain.objects.get(pk=pk)
        fields = ['dkim', 'app_domain']
        for field in fields:
            validate_sending_domain_field(pk, field)
        return Response({key: getattr(
            domain, '{}_status'.format(key)) for key in fields})
