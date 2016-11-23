from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class AbuseApp(AppConfig):
    name = 'munch.apps.abuse'
    verbose_name = _("Abuse")
