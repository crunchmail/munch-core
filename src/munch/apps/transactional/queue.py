import sys
import logging

from django.conf import settings
from django.utils.module_loading import import_string
from slimta.queue import QueueError
from slimta.relay.blackhole import BlackholeRelay


from munch.core.mail.backend import Backend

log = logging.getLogger(__name__)


class QueueStartupFatalError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return 'FATAL, abording startup: {}'.format(self.msg)


class TransactionalQueue:
    def __init__(self, relay):
        # Initialize default queue policies
        self.queue_policies = []
        for path in settings.TRANSACTIONAL.get('QUEUE_POLICIES', []):
            try:
                policy = import_string(path)
            except ImportError:
                raise QueueStartupFatalError(
                    '{} points to inexistant queue policy'.format(path))
            except TypeError:
                raise QueueStartupFatalError(
                    '{} is not a valid QueuePolicy'.format(path))
            self.queue_policies.append(policy())

    def kill(self):
        pass

    def enqueue(self, envelope):
        try:
            envelopes = self._run_policies(envelope)
        except QueueError as exc:
            return [(envelope, exc)]
        ids = [self._initiate_attempt(env) for env in envelopes]
        results = list(zip(envelopes, ids))
        return results

    def _run_policies(self, envelope):
        results = [envelope]

        def recurse(current, i):
            try:
                policy = self.queue_policies[i]
            except IndexError:
                return
            ret = policy.apply(current)
            if ret:
                results.remove(current)
                results.extend(ret)
                for env in ret:
                    recurse(env, i + 1)
            else:
                recurse(current, i + 1)

        recurse(envelope, 0)
        return results

    def _initiate_attempt(self, envelope, attempts=0):
        """ First method called for a sending attempt """
        backend = Backend(
            build_envelope_task_path=(
                'munch.apps.transactional.utils.get_envelope'),
            mailstatus_class_path=(
                'munch.apps.transactional.models.MailStatus'),
            record_status_task_path=(
                'munch.apps.transactional.status.record_status'))
        return backend.send_envelope(envelope, attempts=attempts)


def setup_queue():
    # We only need a dummy slimta relay here
    # only to allow for queue creation
    relay = BlackholeRelay()

    # Set up celery queue
    queue = TransactionalQueue(relay)

    return relay, queue


try:
    # This has to be done, on import, so that celery tasks get set up and
    # available to workers
    relay, queue = setup_queue()
except QueueStartupFatalError:
    log.error("Error while starting Queue", exc_info=True)
    sys.exit(1)
