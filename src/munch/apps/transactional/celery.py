import sys

from celery.signals import celeryd_after_setup

from munch.core.utils import get_worker_types
from munch.core.celery import catch_exception
from munch.core.celery import munch_tasks_router


def register_tasks():
    tasks_map = {
        'status': [
            'munch.apps.transactional.status.SendWebhook',
            'munch.apps.transactional.status.CreateDSN',
            'munch.apps.transactional.status.ForwardDSN',
            'munch.apps.transactional.status.HandleDSNStatus',
            'munch.apps.transactional.status.HandleSMTPStatus',
            'munch.apps.transactional.status.record_status'
        ],
    }
    munch_tasks_router.import_tasks_map(tasks_map, 'transactional')


@celeryd_after_setup.connect
@catch_exception
def configure_worker(instance, **kwargs):
    if any([t in get_worker_types() for t in ['status', 'all']]):
        from .status import create_dsn  # noqa
        from .status import forward_dsn  # noqa
        from .status import send_webhook  # noqa
        from .status import record_status  # noqa
        from .status import handle_dsn_status  # noqa
        from .status import handle_smtp_status  # noqa
        sys.stdout.write('[transactional] Registering worker as STATUS...')
        munch_tasks_router.register_as_worker('status')
