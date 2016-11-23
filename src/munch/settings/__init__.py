import os

from .base import *  # noqa

if os.environ.get(
        'DJANGO_SETTINGS_MODULE', 'munch.settings') == 'munch.settings':
    from .local import *  # noqa
