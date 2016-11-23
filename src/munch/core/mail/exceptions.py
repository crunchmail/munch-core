import logging
from celery.exceptions import Reject

log = logging.getLogger(__name__)


class SoftFailure(Exception):
    pass


class HardFailure(Exception):
    pass


class RejectMissingField(Reject):
    def __init__(self, field, recipient, headers=None, *args, **kwargs):
        msg = 'Missing field {} in received mail'.format(field)
        if headers:
            log.warning(msg + str(headers))
        else:
            log.warning(msg)

        super().__init__(msg, *args, **kwargs)


class RejectUnknownIdentifier(Reject):
    def __init__(self, identifier, headers=None, *args, **kwargs):
        msg = 'No mail known with Message-Id {}'.format(identifier)
        if headers:
            log.warning(msg + ". Headers: \n{}".format(str(headers)))
        else:
            log.warning(msg)

        super().__init__(msg, *args, **kwargs)


class RejectInvalidDSN(Reject):
    def __init__(self, exc, headers=None, *args, **kwargs):
        if headers:
            log.warning(str(exc) + str(headers))
        else:
            log.warning(str(exc))

        super().__init__(str(exc), *args, **kwargs)


class RejectForbiddenTransition(Reject):
    def __init__(self, obj, exc, *args, **kwargs):
        super().__init__(
            'Forbidden transition on {} : {}'.format(obj, str(exc)),
            *args, **kwargs)
