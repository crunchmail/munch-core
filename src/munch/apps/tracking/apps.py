from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class TrackingApp(AppConfig):
    name = 'munch.apps.tracking'
    verbose_name = _("Tracking")
