import email
import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from slimta.queue import QueueError
from slimta.policy import QueuePolicy

# DSN tasks
from munch.apps.campaigns.tasks import handle_dsn as campaigns_dsn
from munch.apps.transactional.status import (
    handle_dsn_status as transactional_dsn)
# Unsubscribe tasks
from munch.apps.campaigns.tasks import handle_mail_optout
# Feedback loop tasks
from munch.apps.campaigns.tasks import handle_fbl

from munch.core.utils import get_mail_by_identifier
from munch.core.mail.models import return_path_parser
from munch.core.mail.models import unsubscribe_parser
from munch.core.mail.utils.parsers import extract_domain

log = logging.getLogger(__name__)


class MailHandler:
    def __init__(self, envelope, message):
        self.envelope = envelope
        self.message = message


class AbstractReportHandler(MailHandler):
    CONTENT_TYPE = 'multipart/report'

    @classmethod
    def can_handle(cls, message):
        return (
            (message.get_content_type() == cls.CONTENT_TYPE) and
            (message.get_param('report-type') == cls.REPORT_TYPE))

    def _get_part_by_types(self, types):
        """ Get the firt part of mail matcthing one of mimetypes

        @param types : a list/tuple of mimetypes
        @return headers dict
        """
        parts = self.message.walk()
        part = next((i for i in parts if i.get_content_type() in types), [])
        d = {}
        if part:
            for i in part.get_payload():
                if isinstance(i, email.message.Message):
                    d.update({k: str(v) for k, v in i.items()})
        return d

    def get_report(self):
        parttype = 'message/{}'.format(self.REPORT_TYPE)
        return self._get_part_by_types([parttype])

    def get_original(self):
        """ Gets the original message that caused the report.

        Note that only the headers part is supposed to be included.
        """
        parttypes = ('message/rfc822', 'text/rfc822-headers')
        return self._get_part_by_types(parttypes)


class DSNHandler(AbstractReportHandler):
    REPORT_TYPE = 'delivery-status'

    def apply(self):
        recipient = self.envelope.recipients[0]
        if not return_path_parser.is_valid(recipient):
            log.info('Invalid recipient: {}'.format(recipient))
            return None

        try:
            identifier = return_path_parser.get_uuid(recipient)
            get_mail_by_identifier(identifier)
        except (ValueError, ObjectDoesNotExist):
            log.info('Cannot find any mail with this recipient: {}'.format(
                recipient))
            return

        if identifier.startswith('c-'):
            return campaigns_dsn.apply_async(args=[
                self.message.as_string(), self.get_report()])
        elif identifier.startswith('t-'):
            return transactional_dsn.apply_async(args=[
                self.message.as_string(), self.get_report()])


class ARFHandler(AbstractReportHandler):
    REPORT_TYPE = 'feedback-report'

    def apply(self):
        original = self.get_original()
        return_path = original.get('Return-Path')
        if not return_path_parser.is_valid(return_path):
            log.info('Invalid Return-Path: {}'.format(return_path))
            return None

        try:
            identifier = return_path_parser.get_uuid(return_path)
            get_mail_by_identifier(identifier)
        except (ValueError, ObjectDoesNotExist):
            log.info('Cannot find any mail with this Return-Path: {}'.format(
                return_path))
            return

        original = self.get_original()
        if not original:
            log.info('Empty original message')
            return

        return handle_fbl.apply_async(args=[
            self.message.as_string(), original, self.get_report()])


class UnsubscribeHandler(MailHandler):
    def apply(self):
        recipient = self.envelope.recipients[0]
        if not unsubscribe_parser.is_valid(recipient):
            log.info('Invalid recipient: {}'.format(recipient))
            return None

        try:
            identifier = unsubscribe_parser.get_uuid(recipient)
            get_mail_by_identifier(identifier)
        except (ValueError, ObjectDoesNotExist):
            log.info('Cannot find any mail with this recipient: {}'.format(
                recipient))
            return

        return handle_mail_optout.apply_async(
            args=[dict(self.message)])

    @classmethod
    def can_handle(cls, msg):
        """
        Unsubscribe are just plain email, so there is no particular format.
        """
        return True


class BackMuncherQueuePolicy(QueuePolicy):
    def apply(self, envelope):
        if not envelope.recipients:
            raise QueueError('Missing recipient')
        recipient = envelope.recipients[0]

        if extract_domain(recipient) != settings.RETURNPATH_DOMAIN:
            raise QueueError('Domain not valid')

        message = email.message_from_bytes(
            envelope.flatten()[0] + envelope.flatten()[1])

        # Check recipient prefix
        prefix_allowed = False
        for prefix in ['return-', 'unsubscribe-', 'abuse']:
            if recipient.startswith(prefix):
                prefix_allowed = True
                break
        if not prefix_allowed:
            raise QueueError('Prefix not allowed')

        # Find handler
        handler_found = False
        for handler in [DSNHandler, ARFHandler, UnsubscribeHandler]:
            if handler.can_handle(message):
                log.info('Handler {} can handle'.format(handler.__name__))
                handler = handler(envelope, message)
                handler_found = True
                break
        if not handler_found:
            raise QueueError('No handler found')
        handler.apply()


class Queue:
    def __init__(self, relay):
        self.policy = BackMuncherQueuePolicy()

    def kill(self):
        pass

    def enqueue(self, envelope):
        try:
            envelope = self.policy.apply(envelope)
        except QueueError as exc:
            return [(envelope, exc)]
        return [(envelope, 0)]
