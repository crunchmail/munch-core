from munch.core.utils.filters import DRFFilterSet

from ...models import SendingDomain


class SendingDomainFilter(DRFFilterSet):
    class Meta:
        model = SendingDomain
        fields = ['name', 'dkim_status']
        order_by = True
