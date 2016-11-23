import django_filters

from munch.core.utils.filters import DRFFilterSet

from ...models import OptOut


class OptOutFilter(DRFFilterSet):
    address = django_filters.CharFilter('address')

    class Meta:
        model = OptOut
        fields = ['address', 'origin', 'creation_date', 'identifier']
        order_by = True
