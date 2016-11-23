from django.db import models
from django.utils.translation import ugettext_lazy as _


class DomainCheckField(models.CharField):
    """ To reflects the status of a configuration check on a domain. """
    OK = 'ok'
    NOT_CONFIGURED = 'ko'
    BADLY_CONFIGURED = 'bad'
    PENDING = 'pending'
    UNKNOWN = 'unknown'

    choices = (
        (OK, _('Configured')),
        (NOT_CONFIGURED, _('Not configured')),
        (BADLY_CONFIGURED, _('Badly configured')),
        (PENDING, _('Checking')),
        (UNKNOWN, _('Unknown')))

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 10
        kwargs['choices'] = self.choices
        kwargs['default'] = self.UNKNOWN
        super().__init__(*args, **kwargs)
