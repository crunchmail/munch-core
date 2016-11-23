from rest_framework import mixins
from rest_framework import viewsets

from munch.core.utils.views import OrganizationOwnedViewSetMixin

from ...models import OptOut
from .filters import OptOutFilter
from .serializers import OptOutSerializer


class OptOutViewSet(
        OrganizationOwnedViewSetMixin, mixins.CreateModelMixin,
        viewsets.ReadOnlyModelViewSet):
    model = OptOut
    serializer_class = OptOutSerializer
    filter_class = OptOutFilter
