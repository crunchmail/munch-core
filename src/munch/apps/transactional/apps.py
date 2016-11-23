from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class TransactionalConfig(AppConfig):
    name = 'munch.apps.transactional'
    verbose_name = _("Transactional")

    def ready(self):
        import munch.apps.transactional.signals  # noqa
        import munch.apps.transactional.api.v1.urls  # noqa
