from django.conf import settings
from slimta.policy import QueuePolicy

from munch.core.mail.utils import mk_msgid


class Remove(QueuePolicy):
    """
    Remove internal headers to avoid spoofing
    """
    def apply(self, envelope):
        for header in settings.TRANSACTIONAL.get('HEADERS_TO_REMOVE'):
            del envelope.headers[header]


class AddMessageIdHeader(QueuePolicy):
    """
    Add a Message-ID header if absent with a custom msgid domain
    """
    def apply(self, envelope):
        if 'message-id' not in envelope.headers:
            envelope.headers['Message-Id'] = mk_msgid()
