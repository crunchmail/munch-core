import logging

from munch.core.utils.tasks import task_autoretry
from munch.core.mail.exceptions import SoftFailure
from munch.core.mail.exceptions import HardFailure
from munch.core.mail.exceptions import RejectUnknownIdentifier

from .models import Mail

log = logging.getLogger(__name__)


def get_envelope(identifier, **kwargs):
    try:
        return Mail.objects.get(identifier=identifier).as_envelope()
    except Mail.DoesNotExist as exc:
        raise SoftFailure(exc)


def get_message_from_identifier(identifier, *kwargs):
    try:
        return Mail.objects.get(identifier=identifier).as_message()
    except Mail.DoesNotExist as exc:
        raise SoftFailure(exc)


def get_mail_or_raise(identifier):
    """ Fetch the http stored returnpath

    See http_returnpath policy for the inverse action (storing)

    :param: X-CM-Message-Id
    :return: MailMetadata
    """

    try:
        mail = Mail.objects.get(identifier=identifier)
    except Mail.DoesNotExist:
        raise RejectUnknownIdentifier(identifier=identifier)
    return mail


@task_autoretry(
    max_retries=None, autoretry_on=(Exception, ),
    autoretry_exclude=(SoftFailure, HardFailure),
    retry_message='Error while trying to record_status. Retrying.')
def record_status(mailstatus, identifier, relay_ehlo, reply=None):
    """ Save MailStatus and send SMTP Status task """
    log.debug('[{}] Recording "{}" status...'.format(
        identifier, mailstatus.status))
    try:
        mail_metadata = get_mail_or_raise(identifier)
        mailstatus.mail = mail_metadata
        mailstatus.save()
    except (SoftFailure, RejectUnknownIdentifier) as exc:
        raise SoftFailure(exc)
