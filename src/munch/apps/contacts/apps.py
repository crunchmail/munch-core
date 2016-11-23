from django.apps import AppConfig


class ContactsApp(AppConfig):
    name = 'munch.apps.contacts'
    verbose_name = 'Contacts'

    def ready(self):
        import munch.apps.contacts.urls  # noqa
        import munch.apps.contacts.api.v1.urls  # noqa
