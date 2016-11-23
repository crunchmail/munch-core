import logging

from django.conf import settings
from django.utils.module_loading import import_string
from django.core.mail.backends.base import BaseEmailBackend

from munch.core.mail.utils import extract_domain
from munch.core.mail.utils import mk_base64_uuid
from munch.core.mail.models import AbstractMailStatus

log = logging.getLogger(__name__)


class DummyBackend(BaseEmailBackend):
    """ This is a dummy backend that doesn't send any mail """
    def __init__(
            self,
            mailstatus_class_path=None,
            record_status_task_path=None,
            *args, **kwargs):

        self.mailstatus_class_path = mailstatus_class_path
        self.record_status_task_path = record_status_task_path

        if self.mailstatus_class_path:
            self.mailstatus_class = import_string(self.mailstatus_class_path)
        if self.record_status_task_path:
            self.record_status_task = import_string(
                self.record_status_task_path)

    def _record_sending(self, identifier, recipient):
        if self.mailstatus_class_path:
            mailstatus = self.mailstatus_class(
                status=AbstractMailStatus.SENDING,
                destination_domain=extract_domain(recipient))
            self.record_status_task(
                mailstatus, identifier,
                'dummy-localhost')

    def send_envelope(self, envelope, attempts=0):
        self._record_sending(envelope.headers.get(
            settings.X_MESSAGE_ID_HEADER), envelope.recipients[0])

    def send_message(self, identifier, recipient, headers, attempts=0):
        self._record_sending(identifier, recipient)

    # To be used by Django as a standard email backend
    def send_messages(self, email_messages):
        if not email_messages:
            return
        for message in email_messages:
            self._record_sending(mk_base64_uuid(), message.to[0])
        return len(email_messages)

    def send_simple_message(self, message):
        self._record_sending(mk_base64_uuid(), message.to[0])

    def send_simple_envelope(self, envelope):
        self._record_sending(mk_base64_uuid(), envelope.recipients[0])


def get_backend():
    return import_string(settings.MASS_EMAIL_BACKEND)


def pre_save_mailstatus_signal(*args, **kwargs):
    base = settings.MASS_EMAIL_BACKEND.split('.')[0]
    import_path = '{}.signals.pre_save_mailstatus'.format(base)
    try:
        signal = import_string(import_path)
        return signal(*args, **kwargs)
    except ImportError as err:
        log.debug('Trying to import "{}", but failed...{}'.format(
            import_path, str(err)))


def post_save_mailstatus_signal(*args, **kwargs):
    base = settings.MASS_EMAIL_BACKEND.split('.')[0]
    import_path = '{}.signals.post_save_mailstatus'.format(base)
    try:
        signal = import_string(import_path)
        return signal(*args, **kwargs)
    except ImportError as err:
        log.debug('Trying to import "{}", but failed...{}'.format(
            import_path, str(err)))


Backend = get_backend()
