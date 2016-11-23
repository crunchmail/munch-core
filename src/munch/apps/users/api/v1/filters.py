from munch.core.utils.filters import DRFFilterSet

from ...models import MunchUser


"""
Handles all filtering/ordering for API viewsets.

Default ordering is :
- (if defined) first item of order_by
- (else) first item of fields
"""


class MunchUserFilter(DRFFilterSet):
    class Meta:
        model = MunchUser
        fields = ['identifier']
        order_by = True
