import os
import sys
import logging
from functools import wraps

import celery
from celery.signals import celeryd_after_setup
from kombu import Queue

from django.conf import settings

from munch.core.utils import get_worker_types

log = logging.getLogger('munch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'munch.settings')


def catch_exception(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except Exception as err:
            sys.stderr.write(str(err))
            raise
    return wrapper


class Celery(celery.Celery):
    def on_configure(self):
        if hasattr(settings, 'RAVEN_CONFIG'):
            from raven import Client
            from raven.contrib.celery import register_signal
            from raven.contrib.celery import register_logger_signal
            client = Client(settings.RAVEN_CONFIG.get('dsn'))
            register_logger_signal(client)
            register_signal(client)


class CeleryRouteMap(object):
    def __init__(self, app):
        self.app = app

        self.exchange = settings.CELERY_DEFAULT_EXCHANGE
        self.exchange_type = settings.CELERY_DEFAULT_EXCHANGE_TYPE

        self.queues = {
            'default': {
                'name': settings.CELERY_DEFAULT_QUEUE,
                'routing_key': settings.CELERY_DEFAULT_ROUTING_KEY
            }
        }
        self.routes = {}

    def add_queue(self, worker_type, queue):
        self.app.amqp.queues.add(
            Queue(
                queue, routing_key='{}.#'.format(queue),
                queue_arguments={'x-max-priority': 100}
            )
        )
        self.queues.update({
            worker_type: {'name': queue, 'routing_key': queue}})
        log.debug('Added queue {} for {} workers'.format(
            queue, worker_type.upper()))

    def register_route(self, task, worker_type, munch_app):
        if worker_type not in self.queues:
            raise ValueError(
                'Can not register celery route. '
                'No queue defined for worker_type {}'.format(
                    worker_type.upper()))
        self.routes.update({task: {'worker': worker_type, 'key': munch_app}})
        log.debug(
            'Registered route for {} on {} workers'.format(
                task, worker_type.upper()))

    def import_tasks_map(self, tasks_map, munch_app):
        for worker, tasks in tasks_map.items():
            for task in tasks:
                self.register_route(task, worker, munch_app)

    def lookup_route(self, task):
        if task in self.routes:
            worker = self.routes.get(task)['worker']
            key = self.routes.get(task)['key']
            queue = self.queues.get(worker)
            return {
                'queue': queue['name'],
                'exchange': self.exchange,
                'exchange_type': self.exchange_type,
                'routing_key': '{}.{}'.format(queue['routing_key'], key)
            }
        return None

    def register_to_queue(self, queue):
        self.app.amqp.queues.select_add(
            queue, routing_key='{}.#'.format(queue),
            queue_arguments={'x-max-priority': 100})

    def register_as_worker(self, worker_type):
        if worker_type not in self.queues:
            raise ValueError(
                'Can not register as worker {}. '
                'No queue defined for this worker_type'.format(
                    worker_type.upper()))
        self.register_to_queue(self.queues[worker_type]['name'])

    def get_queue_for(self, worker_type):
        return self.queues.get(worker_type, 'default')['name']

    def get_workers_map(self):
        workers_map = {}
        for k, v in self.routes.items():
            workers_map.setdefault(v['worker'], []).append(k)
        return workers_map


class CeleryRouter(object):
    def route_for_task(self, task, args=None, kwargs=None):
        return munch_tasks_router.lookup_route(task)


# Celery App initialization
app = Celery('munch', broker=settings.BROKER_URL)
app.config_from_object('django.conf:settings')

munch_tasks_router = CeleryRouteMap(app)


# Queues, Tasks and worker registration methods for munch.core
def add_queues():
    munch_tasks_router.add_queue('core', 'munch.core')
    munch_tasks_router.add_queue('status', 'munch.status')
    munch_tasks_router.add_queue('gc', 'munch.gc')


def register_tasks():
    tasks_map = {
        'gc': ['munch.core.mail.tasks.purge_raw_mail']
    }
    munch_tasks_router.import_tasks_map(tasks_map, 'munch')


@celeryd_after_setup.connect
@catch_exception
def configure_worker(instance, **kwargs):
    if any([t in get_worker_types() for t in ['gc', 'all']]):
        from .mail.tasks import purge_raw_mail  # noqa
        sys.stdout.write(
            '[core-app] Registering worker as GARBAGE COLLECTOR...')
        munch_tasks_router.register_as_worker('gc')
