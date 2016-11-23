import django_filters

from munch.core.utils.filters import DRFFilterSet

from ...models import Mail
from ...models import MailStatus


class MailFilter(DRFFilterSet):
    class Meta:
        model = Mail
        fields = ['batch']
        order_by = True


class MailStatusFilter(DRFFilterSet):
    address = django_filters.CharFilter(name='mail__recipient')

    class Meta:
        model = MailStatus
        fields = ['address', 'creation_date', 'status']
        order_by = True
