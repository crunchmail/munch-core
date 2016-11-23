import re
import time
import email
import logging
import datetime
from email.utils import parseaddr
from email.utils import formatdate

import celery
import requests
from django.conf import settings
from slimta.envelope import Envelope

from munch.core.mail.backend import Backend
from munch.core.mail.utils import extract_domain
from munch.core.mail.utils import parse_email_date
from munch.core.utils.tasks import task_autoretry
from munch.core.mail.utils.dsn import DSN
from munch.core.mail.utils.dsn import DSNParser
from munch.core.mail.utils.dsn import InvalidDSNError
from munch.core.mail.exceptions import SoftFailure
from munch.core.mail.exceptions import HardFailure
from munch.core.mail.exceptions import RejectMissingField
from munch.core.mail.exceptions import RejectInvalidDSN

from .models import Mail
from .models import MailStatus
from .utils import get_envelope_from_identifier
from .policies.relay.headers import return_path_parser

log = logging.getLogger(__name__)


class SendWebhook(celery.task.Task):
    max_retries = None

    # SMTP status map
    # It can be used with first digit of both ESMTP and SMTP status codes
    @staticmethod
    def get_http_returnpath(identifier, headers):
        """ Fetch the http stored returnpath

        See http_returnpath policy for the inverse action (storing)

        :param: the CM-Message-Id mail address of just sent envelope
        :return: the URL to notify status updates
        """
        mail = Mail.objects.get(identifier=identifier)
        http_return_path = mail.headers.get(
            settings.X_HTTP_DSN_RETURN_PATH_HEADER, None)
        if http_return_path:
            return http_return_path.strip()

    def http_post(self, url, data):
        tmp_err_msg = None

        try:
            response = requests.post(url, json=data)
        except requests.exceptions.ConnectionError as e:
            tmp_err_msg = (
                'Failed to log status "{}" to {} : {}'.format(
                    data['status'], url, str(e)))
        else:
            if response.status_code in (200, 201):
                log.info('Logged "{}" status to {}'.format(
                    data['status'], url))
            else:
                tmp_err_msg = (
                    'Failed to log status "{}" to {} (HTTP {})'.format(
                        data['status'], url, response.status_code))
        finally:
            if tmp_err_msg is not None:
                try:
                    self.retry(
                        countdown=settings.TRANSACTIONAL[
                            'STATUS_WEBHOOK_RETRY_INTERVAL'],
                        max_retries=settings.TRANSACTIONAL[
                            'STATUS_WEBHOOK_RETRIES'])
                except celery.exceptions.MaxRetriesExceededError:
                    log.warn(
                        'Too many errors while sending webhook, giving up.',
                        exc_info=True, extra={'error_message': tmp_err_msg})
                except celery.exceptions.Retry:
                    # In case we just queued a retry task
                    log.info(
                        'Error while sending webhook (will retry later)',
                        exc_info=True, extra={'error_message': tmp_err_msg})
                    raise

    def log_no_http_returnpath(self, identifier):
        # may become log.info() once we handle properly the sending of
        # bounces via SMTP
        log.info(
            '[{}] No {}, unable to HTTP-push the status'.format(
                identifier, settings.X_HTTP_DSN_RETURN_PATH_HEADER))

    def __call__(self, identifier, headers, data):
        webhook_url = self.get_http_returnpath(identifier, headers)
        if not webhook_url:
            self.log_no_http_returnpath(identifier)
        else:
            self.http_post(webhook_url, data)


send_webhook = SendWebhook()


class SendDSN(celery.task.Task):
    @staticmethod
    def get_smtp_returnpath(identifier, headers, mail=None):
        """ Fetch the smtp stored returnpath

        See smtp_returnpath policy for the inverse action (storing)

        :param: the Return-Path mail address of just sent envelope
        :return: the URL to notify status updates
        """
        if not mail:
            mail = Mail.objects.get(identifier=identifier)
        if mail.headers.get(
                settings.X_HTTP_DSN_RETURN_PATH_HEADER, None):
            return mail.headers.get(
                settings.X_SMTP_DSN_RETURN_PATH_HEADER, None)
        else:
            return mail.headers.get(
                settings.X_SMTP_DSN_RETURN_PATH_HEADER, mail.sender)

    def send_dsn(self, envelope, recipient):
        backend = Backend()

        # We set an empty MAILFROM since DSN don't have a Return-Path
        envelope.sender = ''
        envelope.recipients = [recipient]
        backend.send_simple_envelope(envelope)


class CreateDSN(SendDSN):
    max_retries = None

    def __call__(self, identifier, headers, client, reply, recipient,
                 status_date, reporting_mta):

        body = "[message omitted] [{}]".format(identifier).encode('utf-8')
        remote_mta = False
        if reply.address:
            remote_mta = reply.address[0]
        dsn = DSN(dsn_from=settings.TRANSACTIONAL.get('SMTP_DSN_ADDRESS'),
                  dsn_to=recipient)

        # convert status_date (datetime) to a string usable in DSN
        timeval = time.mktime(status_date.timetuple())
        dsn_date = formatdate(timeval=timeval, localtime=True)
        dsn_message = dsn.generate(
            original_headers=headers, original_body=body,
            reply_code=reply.code, reply_message=reply.message,
            reporting_mta=reporting_mta, remote_mta=remote_mta, date=dsn_date,
            report_headers={
                settings.TRANSACTIONAL['X_MESSAGE_ID_HEADER']: identifier})

        envelope = Envelope()
        envelope.parse(dsn_message)

        self.send_dsn(envelope, recipient)


create_dsn = CreateDSN()


class ForwardDSN(SendDSN):
    max_retries = None

    def __call__(self, original_dsn, recipient):

        envelope = Envelope()
        envelope.parse(original_dsn.encode('utf-8'))

        self.send_dsn(envelope, recipient)


forward_dsn = ForwardDSN()


class HandleDSNStatus(celery.task.Task):
    max_retries = None

    RETURNPATH_ADDR = 'To'
    DATE_FIELD = 'Arrival-Date'

    def __call__(self, original_dsn, report_headers):
        original_dsn = email.message_from_string(original_dsn)
        try:
            return_path = parseaddr(original_dsn[self.RETURNPATH_ADDR])[1]
            message_id = return_path_parser.get_uuid(return_path)
        except (KeyError, ValueError):
            raise RejectMissingField(
                self.RETURNPATH_ADDR, 'unknown', headers=original_dsn)

        try:
            dsn = DSNParser(report_headers)
        except InvalidDSNError as e:
            raise RejectInvalidDSN(e, headers=report_headers)

        try:
            # 2 fallbacks for the date
            if dsn.date:
                date = dsn.date
            else:
                if 'Date' in original_dsn:
                    date = parse_email_date(original_dsn['Date'])
                else:
                    date = datetime.datetime.now()

            status = dsn.get_next_mailstatus()

            # Record status
            if dsn.original_recipient:
                recipient = dsn.original_recipient
            else:
                recipient = dsn.final_recipient

            original_domain = extract_domain(recipient)

            # We use a generic source_ip for this status
            # since it is not linked to one of our workers
            raw_msg = ''
            if dsn.smtp_status:
                raw_msg = dsn.smtp_status + ' '
            if dsn.msg:
                raw_msg += dsn.msg.replace('\n', ' ')
            mailstatus = MailStatus(
                status_code=dsn.esmtp_status,
                raw_msg=raw_msg.strip(),
                status=status, destination_domain=original_domain,
                source_ip='0.0.0.0')
            record_status(mailstatus, message_id, '0.0.0.0')

            # Send Webhook
            data = {
                'status': status,
                'message': dsn.msg.replace('\n', ' '),
                'smtp_status': dsn.smtp_status or 'unknown',
                'esmtp_status': dsn.esmtp_status,
                'date': date.isoformat(),
                'recipient': recipient
            }
        except Exception as exc:
            log.error(
                'Error while handling DSN Status. Retrying.', exc_info=True)
            self.retry(exc=exc)

        send_webhook.apply_async(
            args=[message_id, original_dsn.as_string(), data])

        # Forward DSN by mail
        # Only if status is Bounced or Dropped
        if status in [MailStatus.BOUNCED, MailStatus.DROPPED]:
            smtp_return_path = SendDSN.get_smtp_returnpath(
                message_id, original_dsn)
            if smtp_return_path:
                # First, replace the the DSN To: (our return address) by the
                # original sender so that it appears properly
                original_dsn.replace_header('To', smtp_return_path)
                forward_dsn.apply_async(
                    args=[original_dsn.as_string(), smtp_return_path])

        else:
            log.info(
                "[{}] Won't forward this DSN because it's "
                "not a failure one.".format(message_id))


handle_dsn_status = HandleDSNStatus()


class HandleSMTPStatus(celery.task.Task):
    max_retries = None

    REGEXP_ESMTP_STATUS = re.compile(
        r'^(?P<esmtp_status>\d+\.\d+\.\d+)\s+(?P<message>.*)')

    @classmethod
    def _extract_esmtp_status(cls, reply):
        """
        :type reply: slimta.smtp.reply.Reply
        :return: a ESMTP status code (ex: "2.0.0") or "unknown"
        :rtype str:
        """
        m = cls.REGEXP_ESMTP_STATUS.match(reply.message)
        if m:
            return m.group('esmtp_status')
        else:
            return 'unknown'

    def __call__(self, status, status_date, identifier, reply, relay_ehlo):
        try:
            envelope = get_envelope_from_identifier(
                identifier, only_headers=True)

            webhook_data = {
                'status': status,
                'message': reply.message,
                'smtp_status': reply.code,
                'esmtp_status': self._extract_esmtp_status(reply),
                'date': status_date.isoformat(),
                'recipient': envelope.recipients[0]}
        except Exception as exc:
            log.error(
                'Error while handling SMTP Status. Retrying.', exc_info=True)
            self.retry(exc=exc)

        # Send Webhook
        send_webhook.apply_async(
            [identifier, dict(envelope.headers), webhook_data])

        # Send DSN by mail
        # Only if status is Bounced or Dropped
        if status in [MailStatus.BOUNCED, MailStatus.DROPPED]:
            smtp_return_path = SendDSN.get_smtp_returnpath(
                identifier, envelope.headers)
            if smtp_return_path:
                create_dsn.apply_async([
                    identifier, dict(envelope.headers), envelope.client,
                    reply, smtp_return_path, status_date, relay_ehlo])

        else:
            log.info(
                "[{}] Won't forward this DSN because it's "
                "not a failure one.".format(identifier))


handle_smtp_status = HandleSMTPStatus()


@task_autoretry(
    max_retries=None, autoretry_on=(Exception, ),
    autoretry_exclude=(SoftFailure, HardFailure, ),
    retry_message='Error while trying to record_status. Retrying.')
def record_status(mailstatus, identifier, relay_ehlo, reply=None):
    """ Save MailStatus and send SMTP Status task """
    log.info('[{}] Recording "{}" status...'.format(
        identifier, mailstatus.status))
    try:
        mail = Mail.objects.get(identifier=identifier)
        mailstatus.mail = mail
        mailstatus.save()
        if reply:
            handle_smtp_status.apply_async([
                mailstatus.status, mailstatus.creation_date, identifier,
                reply, relay_ehlo])
    except (SoftFailure, Mail.DoesNotExist) as exc:
        raise SoftFailure(exc)
