from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class DomainsApp(AppConfig):
    name = 'munch.apps.domains'
    verbose_name = _('Domains')

    def ready(self):
        import munch.apps.domains.signals  # noqa
        import munch.apps.domains.api.v1.urls  # noqa
