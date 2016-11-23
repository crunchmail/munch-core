from importlib import import_module
from django.conf import settings

from .celery import app  # noqa
from .celery import munch_tasks_router  # noqa
from .celery import add_queues as add_core_queues
from .celery import register_tasks as register_core_tasks

from .utils import monkey_patch_slimta_exception

default_app_config = 'munch.core.apps.CoreApp'


add_core_queues()
register_core_tasks()


# Register apps queues, tasks and workers
for _app in settings.INSTALLED_APPS:
    try:
        app_celery = import_module('{}.celery'.format(_app))
        try:
            app_celery.add_queues()
        except AttributeError:
            pass
        try:
            app_celery.register_tasks()
        except AttributeError:
            pass
    except ImportError:
        pass


def register_extended_msgpack():
    # Register extended msgpack decoder
    import datetime
    import pytz
    from slimta.smtp.reply import Reply

    import msgpack
    from kombu.serialization import register

    def msgpack_decode(obj):
        def object_hook(obj):
            if '__datetime__' in obj:
                obj = datetime.datetime.strptime(
                    obj['as_str'], "%Y%m%dT%H:%M:%S.%f").replace(
                        tzinfo=pytz.utc)
            elif '__slimta.Reply__' in obj:
                obj = Reply(
                    code=obj['as_dict'].get('code'),
                    message=obj['as_dict'].get('message'),
                    command=obj['as_dict'].get('command'),
                    address=obj['as_dict'].get('address'))
            return obj
        return msgpack.unpackb(obj, object_hook=object_hook, encoding='utf-8')

    def msgpack_encode(obj):
        def hook(obj):
            if isinstance(obj, datetime.datetime):
                return {
                    '__datetime__': True,
                    'as_str': obj.strftime("%Y%m%dT%H:%M:%S.%f")}
            elif isinstance(obj, Reply):
                return {
                    '__slimta.Reply__': True,
                    'as_dict': {
                        'code': obj.code,
                        'address': obj.address,
                        'message': obj.message,
                        'command': obj.command,
                    }
                }
            return obj
        return msgpack.packb(obj, default=hook, use_bin_type=True)

    register(
        'extended-msgpack', msgpack_encode, msgpack_decode,
        content_type='application/x-extended-msgpack',
        content_encoding='binary')


register_extended_msgpack()
monkey_patch_slimta_exception()
