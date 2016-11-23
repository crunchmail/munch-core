from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class CampaignsApp(AppConfig):
    name = 'munch.apps.campaigns'
    verbose_name = _("Campaigns")

    def ready(self):
        import munch.apps.campaigns.signals  # noqa
        import munch.apps.campaigns.api.v1.urls  # noqa
