import sys

from celery.signals import celeryd_after_setup

from munch.core.utils import get_worker_types
from munch.core.celery import catch_exception
from munch.core.celery import munch_tasks_router


def register_tasks():
    tasks_map = {
        'core': ['munch.apps.campaigns.tasks.send_mail'],
        'status': [
            'munch.apps.campaigns.tasks.handle_dsn',
            'munch.apps.campaigns.tasks.handle_fbl',
            'munch.apps.campaigns.tasks.record_status',
            'munch.apps.campaigns.tasks.handle_mail_optout',
        ]
    }
    munch_tasks_router.import_tasks_map(tasks_map, 'campaigns')


@celeryd_after_setup.connect
@catch_exception
def configure_worker(instance, **kwargs):
    worker_types = get_worker_types()
    if any(t in worker_types for t in ['status', 'all']):
        from .tasks import handle_dsn  # noqa
        from .tasks import handle_fbl  # noqa
        from .utils import record_status  # noqa
        from .tasks import handle_mail_optout  # noqa
        sys.stdout.write('[campaigns-app] Registering worker as STATUS...')
        munch_tasks_router.register_as_worker('status')

    if any(t in worker_types for t in ['core', 'all']):
        from .tasks import send_mail  # noqa
        sys.stdout.write('[campaigns-app] Registering worker as CORE...')
        munch_tasks_router.register_as_worker('core')
