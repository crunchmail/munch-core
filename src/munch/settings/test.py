import tempfile
from .base import *  # noqa

from libfaketime import reexec_if_needed
reexec_if_needed()

##########
# Django #
##########
MEDIA_ROOT = tempfile.mkdtemp()
SECRET_KEY = 'i^p%p^(gdh##2@ll*t)3^)1k87yo62)ig2=@sjoj*kas#lk46z'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.environ.get('TEST_PG_NAME', 'munch'),
        'USER': os.environ.get('TEST_PG_USER', 'munch'),
        'PASSWORD': os.environ.get('TEST_PG_PASS', 'munch'),
        'HOST': os.environ.get('TEST_PG_HOST', 'localhost'),
        'PORT': os.environ.get('TEST_PG_PORT', 15432),
    }
}
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get('REDIS_PORT', 'redis://{}:{}/1'.format(
            os.environ.get('TEST_REDIS_HOST', 'localhost'),
            os.environ.get('TEST_REDIS_PORT', 16379))),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

##########
# Celery #
##########
BROKER_BACKEND = 'memory'
CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

##########
# Global #
##########
APPLICATION_URL = 'http://test.munch.example.com'
BYPASS_DNS_CHECKS = True
RETURNPATH_DOMAIN = 'test.munch.example.com'

#############
# Campaigns #
#############
CAMPAIGNS['BYPASS_RECIPIENTS_MX_CHECK'] = True

###########
# Domains #
###########
DOMAINS['DKIM_KEY_CONTENT'] = '"v=DKIM1; k=rsa; t=y; p=CHANGEME"'

################
# Upload store #
################
UPLOAD_STORE['URL'] = 'http://munch.example.com'
UPLOAD_STORE['IMAGE_MAX_WIDTH'] = 600
UPLOAD_STORE['BACKEND'] = (
    'munch.apps.upload_store.backends.LocalFileSystemStorage')

############
# Contacts #
############
CONTACTS = {
    'MAX_BULK_CONTACTS': 10000,
    'EXPIRATIONS': {
        'contact_queues:double-opt-in': timedelta(days=7),
        'contact_queues:bounce-check': timedelta(hours=1),
        'contact_queues:consumed_lifetime': timedelta(days=7),
        'contact_queues:failed_lifetime': timedelta(days=7),
        'contact_lists:double-opt-in': timedelta(days=7),
        'contact_lists:bounce-check': timedelta(hours=1),
        'contact_lists:consumed_lifetime': timedelta(days=7),
        'contact_lists:failed_lifetime': timedelta(days=7)}
}
