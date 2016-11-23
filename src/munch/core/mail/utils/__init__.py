import uuid
import base64
import time
from math import floor
from socket import getfqdn

from django.conf import settings

from munch.apps.domains.fields import DomainCheckField

from .parsers import extract_domain  # noqa
from .parsers import parse_email_date  # noqa
from .parsers import UniqueEmailAddressParser  # noqa


def mk_base64_uuid(prefix=''):
    """
    :return: a base64url encoded uuid
    """
    r_uuid = base64.urlsafe_b64encode(uuid.uuid4().bytes)
    return '{}{}'.format(prefix, r_uuid.decode('ascii').strip('='))


def mk_msgid():
    """
    :return: a unique Message-ID header content
    """
    msgid_domain = settings.MSGID_DOMAIN or getfqdn()
    return '<{0}.{1:.0f}@{2}>'.format(
        uuid.uuid4().hex, floor(time.time()), msgid_domain)


def get_app_url(domain=None, organization=None):
    if domain and domain.app_domain and \
            domain.app_domain_status == DomainCheckField.OK:
        return 'http://{}'.format(domain.app_domain)
    elif organization and organization.settings.nickname:
        scheme, domain = settings.APPLICATION_URL.strip('/').split('://')
        return '{}://{}.{}'.format(
            scheme, organization.settings.nickname, domain)
    elif (organization and organization.parent and
          organization.parent.settings.nickname):
        scheme, domain = settings.APPLICATION_URL.strip('/').split('://')
        return '{}://{}.{}'.format(
            scheme, organization.settings.nickname, domain)
    else:
        return settings.APPLICATION_URL.strip('/')
