import functools

import celery
import celery.exceptions
from celery import task
from celery.exceptions import Reject
from celery.exceptions import IncompleteStream
from celery.utils.log import get_task_logger

log = get_task_logger(__name__)


class AutoRetryTask(celery.task.Task):
    """ A task that will retry automatically on exception

    exceptions triggering retry are all exceptions, excepted celery ones.

    """
    # Builds a list of celery exceptions, excluding warnings
    # workaround https://github.com/celery/celery/pull/2644
    CELERY_EXCEPTIONS = tuple(
        v for k, v in celery.exceptions.__dict__.items()
        if ((k in celery.exceptions.__all__) and (not k.endswith('Warning')))
    ) + (Reject, IncompleteStream)

    def run(self, *args, **kwargs):
        try:
            self.safe_run(*args, **kwargs)
        except Exception as exc:

            if isinstance(exc, self.CELERY_EXCEPTIONS):
                raise
            else:
                log.exception(exc)
                self.retry(exc=exc)

    def safe_run(self, *args, **kwargs):
        raise NotImplementedError


def task_autoretry(*args_task, **kwargs_task):
    # https://github.com/celery/celery/pull/2112
    def real_decorator(func):
        @task(*args_task, **kwargs_task)
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except kwargs_task.get('autoretry_on', Exception) as exc:
                for exclude in kwargs_task.get('autoretry_exclude', []):
                    if isinstance(exc, exclude):
                        log.info(
                            'Wont retry this task because exception '
                            '"{}" is exclude'.format(str(exc)))
                        return
                if kwargs_task.get('retry_message', False):
                    log.error(kwargs_task.get('retry_message'), exc_info=True)
                wrapper.retry(exc=exc)
        return wrapper
    return real_decorator
