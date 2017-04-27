import os
import logging

from django.conf import settings
from django.core.cache import cache
from slimta.policy import QueuePolicy

logger = logging.getLogger(__name__)


class Apply(QueuePolicy):
    """
    Execute abritary policies on file system based on EXEC_QUEUE_POLICIES
    """
    def apply(self, envelope):
        for path in settings.TRANSACTIONAL.get('EXEC_QUEUE_POLICIES'):

            if os.path.exists(path):
                with open(path) as module:

                    ephemeral_context = {}

                    allowed_context = {'__builtins__': {
                        'settings': settings,
                        'cache': cache,
                        'logger': logger,
                        'print': print
                    }}
                    for mod in settings.TRANSACTIONAL.get('EXEC_QUEUE_POLICIES_CONTEXT_BUILTINS'):
                        allowed_context['__builtins__'][m] = __import__(m)

                    try:
                        exec(module.read(), allowed_context, ephemeral_context)
                        ephemeral_context.get('apply')(envelope)
                    except Exception as err:
                        logger.warning(
                            '[{}] Failed to execute "{}" ephemeral '
                            'policy: {}'.format(
                                envelope.headers.get(
                                    settings.TRANSACTIONAL.get(
                                        'X_MESSAGE_ID_HEADER',
                                        'NO-MESSAGE-ID')),
                                path, err))

            else:
                logger.warning(
                    "[{}] Following ephemeral policy doesn't "
                    "exists: {}".format(
                        envelope.headers.get(settings.TRANSACTIONAL.get(
                            'X_MESSAGE_ID_HEADER', 'NO-MESSAGE-ID')),
                        path))
