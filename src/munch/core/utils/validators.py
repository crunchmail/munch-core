import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.deconstruct import deconstructible
from django.utils.translation import ugettext_lazy as _


@deconstructible
class DomainNameValidator(RegexValidator):
    """ Validates against IDNA20013

    See http://www.unicode.org/reports/tr46/#Table_IDNA_Comparisons
    There is not a lot of forbidden domain names with IDN...
    """
    message = _('Enter a valid plain or internationalized domain name value')
    regex = re.compile((
        r'^'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'  # domain...
        r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}(?<!-)\.?)|'  # ...domain
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
    ), re.IGNORECASE)

    def __init__(self, accept_idna=True, **kwargs):
        message = kwargs.get('message')
        self.accept_idna = accept_idna
        super(DomainNameValidator, self).__init__(**kwargs)
        if not self.accept_idna and message is None:
            self.message = _('Enter a valid domain name value')

    def __call__(self, value):
        try:
            super(DomainNameValidator, self).__call__(value)
        except ValidationError as exc:
            if not self.accept_idna:
                raise
            if not value:
                raise
            try:
                idnavalue = value.encode('idna')
            except UnicodeError:
                raise exc
            super(DomainNameValidator, self).__call__(idnavalue)
