import sys

from celery.signals import celeryd_after_setup

from munch.core.utils import get_worker_types
from munch.core.celery import catch_exception
from munch.core.celery import munch_tasks_router


def register_tasks():
    tasks_map = {
        'core': [
            'contacts.status.handle_bounce',
            'contacts.status.handle_bounce_expirations',
            'contacts.status.handle_failed_expirations',
            'contacts.status.handle_opt_ins_expirations',
            'contacts.status.handle_consumed_contacts_expirations'
        ]
    }
    munch_tasks_router.import_tasks_map(tasks_map, 'contacts')


@celeryd_after_setup.connect
@catch_exception
def configure_worker(instance, **kwargs):
    if any(t in get_worker_types() for t in ['core', 'all']):
        from .tasks import handle_bounce  # noqa
        from .tasks import handle_bounce_expirations  # noqa
        from .tasks import handle_failed_expirations  # noqa
        from .tasks import handle_opt_ins_expirations  # noqa
        from .tasks import handle_consumed_contacts_expirations  # noqa

        sys.stdout.write('[contacts-app] Registering worker as CORE...')
        munch_tasks_router.register_as_worker('core')
