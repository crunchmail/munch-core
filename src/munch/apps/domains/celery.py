import sys

from celery.signals import celeryd_after_setup

from munch.core.utils import get_worker_type
from munch.core.celery import catch_exception
from munch.core.celery import munch_tasks_router


def register_tasks():
    tasks_map = {
        'core': [
            'munch.apps.domains.tasks.run_domains_validation',
            'munch.apps.domains.tasks.validate_sending_domain_field'
        ],
    }
    munch_tasks_router.import_tasks_map(tasks_map, 'domains')


@celeryd_after_setup.connect
@catch_exception
def configure_worker(instance, **kwargs):
    if get_worker_type() in ['core', 'all']:
        from .tasks import run_domains_validation  # noqa
        from .tasks import validate_sending_domain_field  # noqa
        sys.stdout.write('[domains-app] Registering worker as CORE...')
        munch_tasks_router.register_as_worker('core')
