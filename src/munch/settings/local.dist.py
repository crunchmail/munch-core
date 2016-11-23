from .base import *
from urllib.parse import urlparse

##########
# Django #
##########

INSTALLED_APPS += ['corsheaders']

MIDDLEWARE_CLASSES.insert(MIDDLEWARE_CLASSES.index('django.middleware.common.CommonMiddleware') - 1, 'corsheaders.middleware.CorsMiddleware')  # noqa
CORS_ORIGIN_ALLOW_ALL = True

DEBUG = True
SECRET_KEY = 'test'
# CONTAINER_IP = urlparse(os.environ.get(
#     'DOCKER_HOST', 'tcp://localhost')).hostname
CONTAINER_IP = '127.0.0.1'
BROKER_URL = 'amqp://guest:guest@{}:5682/munch'.format(CONTAINER_IP)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'munch',
        'USER': 'munch',
        'PASSWORD': 'munch',
        'HOST': CONTAINER_IP,
        'PORT': '15432',
    }
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://{}:16379/1".format(CONTAINER_IP),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

###########
# Logging #
###########
LOGGING['loggers']['munch'] = {
    'handlers': ['console'],
    'filters': [],
    'propagate': False,
    'level': logging.DEBUG,
}
LOGGING['loggers']['mailsend'] = {
    'handlers': ['console'],
    'level': logging.DEBUG,
    'propagate': False
}

##########
# Global #
##########
APPLICATION_URL = 'http://localhost:8000'
MASS_SENDER_DOMAIN = 'localhost'
MASS_EMAIL_BACKEND = 'munch.core.mail.backend.DummyBackend'
BYPASS_DNS_CHECKS = True

#################
# Transactional #
#################
TRANSACTIONAL['SMTP_BIND_HOST'] = '0.0.0.0'
TRANSACTIONAL['SMTP_BIND_PORT'] = 1025
TRANSACTIONAL['SMTP_REQUIRE_CREDENTIALS'] = True
TRANSACTIONAL['SMTP_CREDENTIALS'] = {'admin': 'admin'}
TRANSACTIONAL['SMTP_SMARTHOST_TLS'] = {
    'keyfile': '<path_to>/munch/utils/ssl/postfix.example.com.key.pem',
    'certfile': '<path_to>/munch/utils/ssl/postfix.example.com.cert.pem',
}

#############
# Campaigns #
#############
CAMPAIGNS['SKIP_SPAM_CHECK'] = True
CAMPAIGNS['SKIP_VIRUS_CHECK'] = True
CAMPAIGNS['BYPASS_RECIPIENTS_MX_CHECK'] = True

SPAMD_PORT = 1783
SPAMD_HOST = 'localhost'
CLAMD_PORT = 13310
CLAMD_HOST = 'localhost'
