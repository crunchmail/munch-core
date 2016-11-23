from django.conf import settings
from slimta.policy import QueuePolicy

from munch.core.mail.utils import mk_base64_uuid


class Add(QueuePolicy):
    """
    Add Munch User-Id and Message-Id headers
    """
    def apply(self, envelope):
        envelope.headers[settings.TRANSACTIONAL[
            'X_USER_ID_HEADER']] = str(envelope.user.pk)
        envelope.headers[settings.TRANSACTIONAL[
            'X_MESSAGE_ID_HEADER']] = mk_base64_uuid(prefix='t-')
