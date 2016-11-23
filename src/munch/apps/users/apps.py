from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class UsersApp(AppConfig):
    name = 'munch.apps.users'
    verbose_name = _('Users')

    def ready(self):
        import munch.apps.users.api.v1.urls  # noqa
