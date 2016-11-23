import re
import uuid
import time
from math import floor
from email.generator import Generator
from email.utils import formatdate

from jinja2 import Template
from jinja2 import Environment
from jinja2 import PackageLoader

from .parsers import parse_email_date
from ..models import AbstractMailStatus


class InvalidDSNError(ValueError):
    def __init__(self, msg):
        self.msg = 'Invalid DSN: {}'.format(msg)


class DSNParser:
    """ Delivery status notification

    As described by RFC3464

    Note that only individual DSN (for one recipient) is handled.
    """
    ACTION_DELAYED = 'delayed'
    ACTION_EXPANDED = 'expanded'
    ACTION_RELAYED = 'relayed'
    ACTION_FAILED = 'failed'
    ACTION_DELIVERED = 'delivered'

    r_diagnostic_code = re.compile(
        r'smtp;\s*(?P<smtp_code>\d{3})[ -].*')

    # Map linking mail statuses and DSN esmtp code first digit
    STATUS_MAP = {
        '2': AbstractMailStatus.DELIVERED,
        '5': AbstractMailStatus.BOUNCED,
        '4': AbstractMailStatus.DROPPED
    }

    def __init__(self, headers=None):
        """ Represents/parses the multipart/report

        :type headers: dict
        :param headers: a dict containing DSN headers
        """
        self.headers = headers
        if headers:
            self.parse_headers(headers)

    def parse_headers(self, headers):
        if not self.headers:
            self.headers = headers
        # Check for mandatory DSN report headers
        try:
            self.final_recipient = headers['Final-Recipient']
        except KeyError:
            raise InvalidDSNError('missing Final-Recipient header')
        try:
            self.esmtp_status = headers['Status']
        except KeyError:
            raise InvalidDSNError('missing Status header')
        try:
            self.action = headers.get('Action', '').lower()
        except KeyError:
            raise InvalidDSNError('missing Action header')

        self.msg = headers.get('Diagnostic-Code', '').replace('\n', ' ')
        m = self.r_diagnostic_code.match(self.msg)
        if m:
            self.smtp_status = m.group('smtp_code')
        else:
            self.smtp_status = None

        try:
            self.original_recipient = headers['Original-Recipient']
        except KeyError:
            self.original_recipient = None

        try:
            date_str = headers['Arrival-Date']
        except KeyError:
            self.date = None
        else:
            self.date = parse_email_date(date_str)

    def get_next_mailstatus(self):
        # there are two cases with 4.x.x errors : retry and given up
        if self.action == self.ACTION_DELAYED:
            return AbstractMailStatus.DELAYED

        else:
            try:
                esmtp_first_digit = self.esmtp_status.split('.')[0]
                return self.STATUS_MAP[esmtp_first_digit]
            except KeyError:
                raise ValueError('Invalid DSN: unknown code : {}'.format(
                    self.esmtp_status))

    def as_string(self):
        raw_dsn = ""
        for key, value in self.headers.items():
            raw_dsn += "{}: {}\n".format(key, value)
        return raw_dsn


DEFAULT_SUBJECTS = {
    '2': 'Successful Mail Delivery Report',
    '5': 'Undelivered Mail Returned to Sender',
    '4': 'Undelivered Mail Returned to Sender',
}
DEFAULT_REPORT_DESCRIPTION = {
    '2': 'Delivered Message',
    '5': 'Undelivered Message',
    '4': 'Undelivered Message'
}
ACTIONS_STATUS_MAP = {
    '2': 'delivered',
    '4': 'failed',
    '5': 'failed'
}


class DSN:
    """ Delivery status notification

    As described by RFC3464

    Note that only individual DSN (for one recipient) is handled.
    """

    def __init__(self, dsn_from, dsn_to, subject=None):

        self.context = {
            'boundary': Generator._make_boundary(),
            'from': dsn_from,
            'to': dsn_to,
            'subject': subject,
        }

    def generate(
            self, original_headers, original_body, reply_code, reply_message,
            reporting_mta, remote_mta, date, report_headers={}, template=None):

        # Main part
        timestamp = floor(time.time())
        self.context.update({
            'date': formatdate(localtime=True),
            'identifier': '<{0}.{1:.0f}@{2}>'.format(
                uuid.uuid4().hex, floor(timestamp), reporting_mta),
        })
        if not self.context['subject']:
            self.context.update({
                'subject': DEFAULT_SUBJECTS.get(reply_code[0], None)
            })
        # Report & body
        self.context.update({
            'arrival_date': date,
            'reporting_mta': reporting_mta,
            'remote_mta': remote_mta,
            'report_headers': report_headers,
            'reply_code': reply_code,
            'reply_status': reply_message.split(' ')[0],
            'reply_message': reply_message,
            'action': ACTIONS_STATUS_MAP.get(reply_code[0], 'failed'),
            'original_recipient': original_headers['To'],
        })
        # Original message
        self.context.update({
            'description': DEFAULT_REPORT_DESCRIPTION.get(reply_code[0]),
            'original_headers': original_headers,
            'original_body': original_body.decode('utf-8'),
        })

        environment = Environment(
            loader=PackageLoader('munch.core.mail.utils', 'templates'))
        dsn_template = environment.get_template('dsn.jinja2')

        if template is None:
            dsn_body_template = environment.get_template('dsn.body.jinja2')
        else:
            dsn_body_template = Template(template)

        self.context.update(
            {'dsn_body': dsn_body_template.render(self.context)})

        message = dsn_template.render(self.context)
        return message.encode('utf-8')
