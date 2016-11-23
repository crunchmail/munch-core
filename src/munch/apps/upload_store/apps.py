from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class UploadStoreApp(AppConfig):
    name = 'munch.apps.upload_store'
    verbose_name = _('Upload store')

    def ready(self):
        import munch.apps.upload_store.api.v1.urls  # noqa
