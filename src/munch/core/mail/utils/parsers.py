import re
import email
import datetime

import pytz


def extract_domain(address):
    return address.strip().split('@')[-1]


def parse_email_date(date_str):
    """Parse a RFC2822 date

    It is the missing email.utils.parsedate_tz_to_datetime from python stdlib.

    :param date_str: a date and time, from an email header
    :type date_str: str
    :return: a datetime, with tz info on UTC
    :rtype datetime:
    """
    date_tupple = email.utils.parsedate_tz(date_str)
    date = datetime.datetime.fromtimestamp(email.utils.mktime_tz(
        date_tupple), pytz.utc)
    return date


class UniqueEmailAddressParser:
    """ Handle unique addresses like <prefix><base64-uuid>@<domain>

    Child classes must define "domain" and "prefix" attributes
    """

    def __init__(self, prefix, domain):
        self.prefix = prefix
        self.domain = domain

    # Those tricks to accept callable are here to ease settings overriding in
    # unit tests.

    def _get_domain(self):
        if hasattr(self.domain, '__call__'):
            return self.domain()
        return self.domain

    def _get_prefix(self):
        if hasattr(self.prefix, '__call__'):
            return self.prefix()
        return self.prefix

    def _get_regexp(self):
        return '(?P<prefix>{})(?P<uuid>[\w\d\-_]{{22,25}})@{}'.format(
            self._get_prefix(), self._get_domain())

    def new(self, b64uuid=None):
        """
        :param domain: the mail domain
        :param b64uuid: a base64url-encoded uuid, if omited, a new one is
          picked
        """
        from . import mk_base64_uuid

        if not b64uuid:
            b64uuid = mk_base64_uuid()
        return '{}{}@{}'.format(
            self._get_prefix(), b64uuid, self._get_domain())

    def is_valid(self, address):
        address = address or ''
        m = re.match(self._get_regexp(), address)
        return m is not None

    def get_uuid(self, address):
        address = address or ''
        m = re.match(self._get_regexp(), address)
        try:
            return m.group('uuid')
        except AttributeError:
            raise ValueError('Not a valid unique address')
