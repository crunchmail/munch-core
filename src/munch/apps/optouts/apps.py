from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class OptOutApp(AppConfig):
    name = 'munch.apps.optouts'
    verbose_name = _("Opt-out")

    def ready(self):
        import munch.apps.optouts.api.v1.urls  # noqa
