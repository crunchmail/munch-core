import logging
import email
from email.utils import parseaddr

import django_fsm
from django.utils.timezone import now as utc_now
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError

from munch.core.mail.backend import Backend
from munch.core.utils.tasks import task_autoretry
from munch.core.utils import get_mail_by_identifier
from munch.core.mail.utils import parse_email_date
from munch.core.mail.utils.dsn import DSNParser
from munch.core.mail.utils.dsn import InvalidDSNError
from munch.core.mail.models import return_path_parser
from munch.core.mail.models import unsubscribe_parser
from munch.core.mail.exceptions import RejectForbiddenTransition
from munch.apps.optouts.models import OptOut

from .validators import validate_existing_mail_domain

from .models import Mail
from .models import MailStatus
from .models import Message


log = logging.getLogger(__name__)


@task_autoretry(
    autoretry_on=(Exception, ),
    default_retry_delay=60 * 3,
    max_retries=(2 * 7 * 24 * 60 * 60) / 180,
    retry_message='Error while trying to build email. Retrying')
def send_mail(mail_pk):
    m = Mail.objects.get(pk=mail_pk)
    try:
        # Check if the recipient's domain has a MX record
        validate_existing_mail_domain(m.recipient)
    except ValidationError as exc:
        # No MX record, set status to IGNORED
        log.info('[{}] Ignored recipient {}, MX check failed'.format(
            m.identifier, m.recipient))
        try:
            MailStatus.objects.create(
                mail=m, status=MailStatus.IGNORED,
                creation_date=utc_now(), raw_msg=exc)
        except django_fsm.TransitionNotAllowed as e:
            raise RejectForbiddenTransition(m, e)
        return 'Ignored {}'.format(m.pk)
    else:
        log.info('[{}] Queueing email for recipient {}'.format(
            m.identifier, m.recipient))
        # explicitly gets the backend asking for systematic DSN.
        backend = Backend(
            mailstatus_class_path='munch.apps.campaigns.models.MailStatus',
            build_envelope_task_path=(
                'munch.apps.campaigns.utils.get_envelope'),
            record_status_task_path=(
                'munch.apps.campaigns.utils.record_status'))
        backend.send_message(
            m.identifier, m.recipient, m.get_headers(), attempts=0)
        return 'Sent {}'.format(m.pk)


@task_autoretry(
    default_retry_delay=60 * 30, max_retries=6 * 24 * 5,
    autoretry_on=(Exception, ), acks_late=True)
def handle_dsn(original_dsn, report_headers):
    """
    Handle a delivery status notification idempotent

    @param headers : a python dict with all the headers of the DSN email.
    """
    ENVELOPE_FIELD = 'To'
    original_dsn = email.message_from_string(original_dsn)

    try:
        envelope = parseaddr(original_dsn[ENVELOPE_FIELD])[1]
    except ValueError:
        log.info('Reject unknown mail: {}'.format(
            original_dsn[ENVELOPE_FIELD]))
        return

    try:
        dsn_report = DSNParser(report_headers)
    except InvalidDSNError as e:
        log.info('Reject invalid DSN: {}'.format(str(e)))
        return

    date = utc_now()
    next_status = dsn_report.get_next_mailstatus()

    try:
        if not return_path_parser.is_valid(envelope):
            log.info('Reject invalid address format: {}'.format(envelope))
            return
        identifier = return_path_parser.get_uuid(envelope)
        mail = Mail.objects.get(identifier=identifier)
    except (Mail.DoesNotExist, ValueError):
        log.info('Reject unknown mail: {}'.format(envelope))
        return
    log.info('Logging new status {} for {}'.format(next_status, mail))
    try:
        ms, created = MailStatus.objects.get_or_create(
            mail=mail, creation_date=date, status=next_status, defaults={
                'raw_msg': dsn_report.msg,
                'status_code': dsn_report.esmtp_status
            })
    except django_fsm.TransitionNotAllowed as e:
        log.info(
            'Reject forbidden dsn status transition '
            '({}): {}\n{}'.format(next_status, mail.identifier, str(e)))
        return
    # If there is nothing left to send, change the state of the message !
    remaining = mail.message.mails.legit_for(
        mail.message).pending().count()
    if remaining == 0:
        mail.message.status = Message.SENT
        mail.message.save()


@task_autoretry(
    default_retry_delay=60 * 30, max_retries=6 * 24 * 5,
    autoretry_on=(Exception, ))
def handle_fbl(main_headers, original_headers, feedback_headers):
    """
    Handle a feedback-loop return (see ARF format)
    Creates the relevant OptOut object, if needed.

    @param main_headers     : headers of the incomming msg \
                                (rfc822), as a dict
    @param original_headers : headers of the original message \
                                (rfc822), as a dict
    @param feedback_headers : headers of the feedback-return \
                                (ARF), as a dict
    """
    main_headers = email.message_from_string(main_headers)

    DATE_FIELD = (main_headers, 'Date')
    ENVELOPE_FIELD = (original_headers, 'Return-Path')

    def get(tupl):
        src, field = tupl
        return src[field]

    try:
        date_str = get(DATE_FIELD)
        envelope = parseaddr(get(ENVELOPE_FIELD))[1]
    except KeyError as e:
        log.info('Invalid feedloop-back, missing field: {}'.format(str(e)))
        return
    except ValueError:
        log.info('Unknown mail: {}'.format(get(ENVELOPE_FIELD)))
        return
    try:
        date = parse_email_date(date_str)
    except ValueError:
        log.info('Invalid date: {}'.format(date_str))
        return

    if not return_path_parser.is_valid(envelope):
        log.info('Reject invalid address format: {}'.format(envelope))
        return

    try:
        mail = get_mail_by_identifier(
            identifier=return_path_parser.get_uuid(envelope))
    except ObjectDoesNotExist:
        log.info('Reject unknown mail: {}'.format(envelope))
        return

    log.info('Unsubscribing {} via fbl'.format(mail.recipient))
    OptOut.objects.create_or_update(
        creation_date=date, identifier=mail.identifier,
        author=mail.get_author(), category=mail.get_category(),
        address=mail.recipient, origin=OptOut.BY_FBL)


@task_autoretry(
    default_retry_delay=60 * 30, max_retries=6 * 24 * 5,
    autoretry_on=(Exception, ))
def handle_mail_optout(headers):
    """
    For the cases a user (or a machine) sends a message to the
    List-Unsubscribe email.

    We do not rely on the sender address at all
    (think about aliases & so on...)

    @param headers the headers of the unsubscription email.
    """
    DATE_FIELD = 'Date'
    UNSUBSCRIBE_ADDR = 'To'

    try:
        date_str = headers[DATE_FIELD]
        unsubscribe_addr = parseaddr(headers[UNSUBSCRIBE_ADDR])[1]
    except KeyError as e:
        log.info('Invalid optout, missing field: {}'.format(str(e)))
        return
    except ValueError:
        log.info('Unknown mail: {}'.format(headers[UNSUBSCRIBE_ADDR]))
        return

    try:
        date = parse_email_date(date_str)
    except ValueError:
        log.info('Invalid date: {}'.format(date_str))
        return

    if not unsubscribe_parser.is_valid(unsubscribe_addr):
        log.info(
            'Reject invalid unsubscribe address format: {}'.format(
                unsubscribe_addr))
        return

    envelope_from = return_path_parser.new(
        unsubscribe_parser.get_uuid(unsubscribe_addr))

    try:
        mail = Mail.objects.get(
            identifier=unsubscribe_parser.get_uuid(unsubscribe_addr))
    except ObjectDoesNotExist:
        log.info('Reject unknown mail: {}'.format(envelope_from))
        return

    existing_optout = OptOut.objects.filter(
        identifier=mail.identifier, origin=OptOut.BY_MAIL).only(
        'pk', 'creation_date')
    if existing_optout:
        optout = existing_optout[0]
        log.info('Already unsubscribed: {} via mail at {} (pk={})'.format(
            mail.recipient, optout.creation_date, optout.pk))
    else:
        log.info('Unsubscribing {} via mail'.format(mail.recipient))
        OptOut.objects.create_or_update(
            author=mail.get_author(), category=mail.get_category(),
            creation_date=date, identifier=mail.identifier,
            address=mail.recipient, origin=OptOut.BY_MAIL)
