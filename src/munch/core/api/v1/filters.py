from ...models import Category
from ...utils.filters import DRFFilterSet


class CategoryFilter(DRFFilterSet):
    class Meta:
        model = Category
        fields = ['name']
        order_by = True
