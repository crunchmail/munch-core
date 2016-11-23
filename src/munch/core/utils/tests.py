import os
import copy
import base64
import shutil
import inspect
from functools import wraps


class HttpBasicTestCaseMixin:
    """ Just a way to build authentication headers

    Example usage :
      self.client.get('/foo',
                      **self.http_basic_headers('user', 'password'))
    """
    def http_basic_headers(self, username, password):
        key = base64.b64encode(
            '{}:{}'.format(username, password).encode('utf-8')).decode()
        return {'HTTP_AUTHORIZATION': 'Basic {}'.format(key)}


class temporary_settings:
    def __enter__(self):
        self.enable()

    def __exit__(self, exc_type, exc_value, traceback):
        self.disable()

    def __call__(self, test_func):
        from django.test import SimpleTestCase
        if isinstance(test_func, type):
            if not issubclass(test_func, SimpleTestCase):
                raise Exception(
                    "Only subclasses of Django SimpleTestCase "
                    "can be decorated with temporary_settings")
            return test_func
        else:
            @wraps(test_func)
            def inner(*args, **kwargs):
                with self:
                    return test_func(*args, **kwargs)
        return inner

    def enable(self):
        from django.conf import settings
        self.wrapped = copy.deepcopy(settings)

    def disable(self):
        from django.conf import settings
        settings._wrapped = self.wrapped
