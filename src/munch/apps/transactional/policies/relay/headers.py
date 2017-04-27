import logging

from django.conf import settings
from slimta.policy import RelayPolicy

from munch.core.mail.utils import UniqueEmailAddressParser

log = logging.getLogger(__name__)

return_path_parser = UniqueEmailAddressParser(
    domain=lambda: settings.RETURNPATH_DOMAIN, prefix='return-')


class RewriteReturnPath(RelayPolicy):
    """ Rewrite existing ReturnPath based on some conditions """
    def apply(self, envelope):
        # If there is X-HTTP-Return-Path
        if settings.TRANSACTIONAL['X_HTTP_DSN_RETURN_PATH_HEADER'] in \
                envelope.headers:
            # Rewrite it
            envelope.sender = return_path_parser.new(
                envelope.headers[settings.TRANSACTIONAL[
                    'X_MESSAGE_ID_HEADER']])
        elif settings.TRANSACTIONAL['X_SMTP_DSN_RETURN_PATH_HEADER'] in \
                envelope.headers:
            # Rewrite it
            envelope.sender = return_path_parser.new(
                envelope.headers[settings.TRANSACTIONAL[
                    'X_MESSAGE_ID_HEADER']])
        # If there is no X-HTTP-Return-Path or X-SMTP-Return-Path
        else:
            log.info(
                '[{}] Keeping original Return-Path ({}) because there are no '
                '"{}" or "{}" headers (then DSN will be sent to original sender).'.format(
                    envelope.headers[settings.TRANSACTIONAL[
                        'X_MESSAGE_ID_HEADER']],
                    envelope.sender,
                    settings.TRANSACTIONAL['X_HTTP_DSN_RETURN_PATH_HEADER'],
                    settings.TRANSACTIONAL['X_SMTP_DSN_RETURN_PATH_HEADER']))
