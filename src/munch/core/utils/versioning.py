from django.utils.translation import ugettext_lazy as _
from rest_framework import exceptions
from rest_framework.versioning import NamespaceVersioning as BaseVersioning


class NamespaceVersioning(BaseVersioning):
    """
    Temporary class
    https://github.com/tomchristie/django-rest-framework/pull/4010
    """

    invalid_version_message = _('Invalid version in namespace.')

    def determine_version(self, request, *args, **kwargs):
        resolver_match = getattr(request, 'resolver_match', None)
        if (resolver_match is None or not resolver_match.namespace):
            return self.default_version
        version = resolver_match.namespace.split(':')[0]
        if not self.is_allowed_version(version):
            raise exceptions.NotFound(self.invalid_version_message)
        return version
