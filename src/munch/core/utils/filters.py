import django_filters
from django import forms
from django.core.validators import EMPTY_VALUES


class DRFFilterSet(django_filters.FilterSet):
    # django-filters default is 'o'
    # DRF default is 'ordering'
    order_by_field = 'ordering'

    def _default_ordering_field(self):
        if self._meta.order_by:
            order_field = self.form.fields[self.order_by_field]
            data = self.form[self.order_by_field].data
            ordered_value = None
            try:
                ordered_value = order_field.clean(data)
            except forms.ValidationError:
                pass
            if ordered_value in EMPTY_VALUES and self.strict:
                ordered_value = self.form.fields[
                    self.order_by_field].choices[0][0]

            return ordered_value
