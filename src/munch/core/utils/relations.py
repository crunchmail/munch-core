from collections import OrderedDict

from django.utils import six
from rest_framework.relations import HyperlinkedRelatedField

from munch.core.utils.permissions import MunchResourcePermission


class ScopedHyperLinkedRelatedField(HyperlinkedRelatedField):
    """ A related field whose content is limited by a permission

    It is already enforced in validation, the purpose of this class is to offer
    the right list in dropdowns.

    Can optionally override the `permission_class` attribute, it must define a
    filter_queryset() function.
    """
    def get_permission(self, model_class):
        permission_class = getattr(self, 'permission_class', None)
        if not permission_class:
            permission_class = MunchResourcePermission.mk_class(model_class)

        return permission_class()

    def get_queryset(self):
        qs = super().get_queryset()
        perm = self.get_permission(qs.model)
        return perm.filter_queryset(qs, self.context.get('request'))

    @property
    def choices(self):
        """
        Copy from parent needed cause @property calls parent
        get_queryset() otherwise (weird isn't it ?)
        """
        queryset = self.get_queryset()
        if queryset is None:
            return {}
        return OrderedDict([
            (
                six.text_type(self.to_representation(item)),
                six.text_type(item)
            )
            for item in queryset
        ])
