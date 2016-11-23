import collections

from rest_framework import viewsets
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.decorators import detail_route

from munch.apps.campaigns.models import Mail
from munch.apps.optouts.models import OptOut
from munch.apps.optouts.api.v1.filters import OptOutFilter
from munch.apps.optouts.api.v1.serializers import OptOutSerializer

from ...models import Category
from ...utils.views import filtered
from ...utils.views import paginated
from ...utils.views import MunchModelViewSetMixin
from ...utils.views import OrganizationOwnedViewSetMixin
from .filters import CategoryFilter
from .serializers import CategorySerializer
from .permissions import CategoryPermission


class CategoryViewSet(
        OrganizationOwnedViewSetMixin,
        MunchModelViewSetMixin,
        viewsets.ModelViewSet):
    model = Category
    serializer_class = CategorySerializer
    filter_class = CategoryFilter
    permission_classes = [CategoryPermission]

    @detail_route(methods=['get'])
    def stats(self, request, pk, format=None):
        category = self.get_object()
        return Response(category.mk_stats())

    @detail_route(methods=['get'])
    def messages_stats(self, request, pk, format=None):
        # FIXME : might be optimized
        stats_dict = [
            collections.OrderedDict([
                ('url', reverse(
                    'campaigns:message-detail',
                    kwargs={'pk': m.pk}, request=request)),
                ('name', m.name),
                ('creation_date', m.creation_date),
                ('stats', m.mk_stats())
            ])
            for m in self.get_object().messages.all()
        ]
        return Response(stats_dict)

    @detail_route(methods=['get'])
    @paginated(OptOutSerializer)
    @filtered(OptOutFilter)
    def opt_outs(self, request, pk, format=None):
        identifiers = Mail.objects.filter(
            message__category=self.get_object()).values_list(
            'identifier', flat=True)
        return OptOut.objects.filter(identifier__in=identifiers)
