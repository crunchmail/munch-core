from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class CoreApp(AppConfig):
    name = 'munch.core'
    verbose_name = _("Core")

    def ready(self):
        import munch.core.signals  # noqa
        import munch.core.api.v1.urls  # noqa
