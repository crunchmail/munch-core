import os
import copy
import logging
from datetime import timedelta

from django.utils.log import DEFAULT_LOGGING
from django.utils.translation import ugettext_lazy as _

##########
# Django #
##########
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = 'CHANGEME'
DEBUG = False
ALLOWED_HOSTS = []
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.postgres',
    # External libs
    'django_humanize',
    'rest_framework',
    # In-project apps
    'munch.core',
    'munch.apps.users',
    'munch.apps.abuse',
    'munch.apps.contacts',
    'munch.apps.campaigns',
    'munch.apps.domains',
    'munch.apps.optouts',
    'munch.apps.hosted',
    'munch.apps.spamcheck',
    'munch.apps.tracking',
    'munch.apps.transactional',
    'munch.apps.upload_store',
    # Mail backend
    'munch_mailsend',
]
MIDDLEWARE_CLASSES = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
]
ROOT_URLCONF = 'munch.urls'
AUTH_USER_MODEL = 'users.MunchUser'
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',  # noqa
        'OPTIONS': {
            'user_attributes': ['identifier', 'first_name', 'last_name'],
            'max_similarity': 0.7,
        }
    },
    {'NAME': 'munch.apps.users.validators.MinimumLengthValidator'},
    {'NAME': 'munch.apps.users.validators.MinimumDigitValidator'},
    {'NAME': 'munch.apps.users.validators.MinimumUppercaseValidator'},
]
WSGI_APPLICATION = 'munch.wsgi.application'
LANGUAGE_CODE = 'en-us'
LANGUAGES = [
    ('fr', _('French')),
    ('en', _('English')),
]
DEFAULT_CHARSET = 'utf-8'
LOCALE_PATHS = [os.path.join(BASE_DIR, 'locale')]
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_L10N = True
USE_TZ = True
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': DEBUG,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
STATIC_URL = '/static/'
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'assets'),
)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'munch.apps.users.backends.SecretMunchUserBackend']
BROKER_URL = 'amqp://localhost:15642'

###########
# Logging #
###########
LOGGING = copy.deepcopy(DEFAULT_LOGGING)
LOGGING['formatters'] = {
    'simple': {
        'format':
            '[%(asctime)s: %(levelname)s/%(module)s.%(funcName)s] %(message)s'
    },
    'django.server': {
        '()': 'django.utils.log.ServerFormatter',
        'format': '[%(server_time)s] %(message)s',
    }
}
# Log every level. Note: need setting DEBUG=True
LOGGING['handlers']['console']['level'] = logging.NOTSET
LOGGING['handlers']['console']['filters'] = []
LOGGING['handlers']['console']['formatter'] = 'simple'
LOGGING['handlers']['django.server'] = {
    'level': 'INFO',
    'class': 'logging.StreamHandler',
    'formatter': 'django.server',
}

# Define custom log handlers for slimta.
# Define a common parent for all slimta children loggers. By default,  we only
# dispatch logs with an INFO level to handlers.
LOGGING['loggers']['slimta'] = {
    'handlers': ['console'],
    'level': logging.INFO,
}
# Define custom project loggers.
LOGGING['loggers']['munch'] = {
    'handlers': ['console'],
    'filters': [],
    'propagate': False,
    'level': logging.INFO,
}
LOGGING['loggers']['munch.errors'] = {
    'handlers': ['mail_admins'],
    'level': logging.ERROR,
    'propagate': False,
}
LOGGING['loggers']['django.server'] = {
    'handlers': ['django.server'],
    'level': 'INFO',
    'propagate': False,
}

##########
# Celery #
##########
CELERY_ACKS_LATE = True
CELERY_CREATE_MISSING_QUEUES = True
CELERY_DEFAULT_QUEUE = 'munch.default'
CELERY_DEFAULT_EXCHANGE = 'munch'
CELERY_DEFAULT_EXCHANGE_TYPE = 'topic'
CELERY_DEFAULT_ROUTING_KEY = 'munch.unknown'
CELERY_ACCEPT_CONTENT = ['extended-msgpack']
CELERY_TASK_SERIALIZER = 'extended-msgpack'
CELERY_RESULT_SERIALIZER = 'extended-msgpack'
CELERY_ROUTES = ('munch.core.celery.CeleryRouter',)

CELERYBEAT_SCHEDULE = {
    'purge_raw_mail': {
        'task': 'munch.core.mail.tasks.purge_raw_mail',
        'schedule': timedelta(hours=2),
    },
    'run_badly_configured_domains_validation': {
        'task': 'munch.apps.domains.tasks.run_domains_validation',
        'args': (['ko', 'bad', 'unknown'], ),
        'schedule': timedelta(minutes=15),
    },
    'run_well_configured_domains_validation': {
        'task': 'munch.apps.domains.tasks.run_domains_validation',
        'args': (['ok'], ),
        'schedule': timedelta(hours=12),
    },
}

##########
# Global #
##########
# Product name appear in email templates and optouts pages
PRODUCT_NAME = 'Munch'
# Default return-path to use (must be backmuncher MX)
RETURNPATH_DOMAIN = 'munch.example.com'
# URL base used for links generation (optouts, tracking, subscriptions, ...)
APPLICATION_URL = 'http://localhost:8000'
# URL base for internal pages (password reset, invitation validation, ...)
HELPDESK_URL = 'http://localhost:8000'

LOGIN_URL = 'rest_framework:login'
LOGIN_REDIRECT_URL = '/v1'

SERVICE_MSG_FROM_NAME = PRODUCT_NAME
SERVICE_MSG_FROM_EMAIL = 'no-reply@{}'.format(RETURNPATH_DOMAIN)
SERVICE_MSG_RETURN_PATH = SERVICE_MSG_FROM_EMAIL
NOTIFICATION_MSG_FROM_NAME = SERVICE_MSG_FROM_NAME
NOTIFICATION_MSG_FROM_EMAIL = SERVICE_MSG_FROM_EMAIL

PASSWORD_MIN_LENGTH = 6
PASSWORD_MIN_DIGIT = 1
PASSWORD_MIN_UPPER = 1

PASSWORD_RESET_TIMEOUT_DAYS = 1
INVITATION_TIMEOUT_DAYS = 15
ACCOUNT_ACTIVATION_TIMEOUT_DAYS = 30

EMAIL_BACKEND = 'munch_mailsend.backend.Backend'
MASS_EMAIL_BACKEND = 'munch_mailsend.backend.Backend'
# May be set True for debug/testing
BYPASS_DNS_CHECKS = False

GOOGLE_FBL_SENDER_ID = 'munch'

MSGID_DOMAIN = None

# Enable performance stats recording via Statsd
STATSD_ENABLED = False
STATSD_HOST = 'localhost'
STATSD_PORT = 8125
STATSD_PREFIX = None
STATSD_MAXUDPSIZE = 512

##################
# Custom headers #
##################
X_USER_ID_HEADER = 'X-Munch-User-Id'
X_POOL_HEADER = 'X-Munch-Pool'
X_MESSAGE_ID_HEADER = 'X-Munch-Message-Id'
X_HTTP_DSN_RETURN_PATH_HEADER = 'X-Munch-HTTP-Return-Path'
X_SMTP_DSN_RETURN_PATH_HEADER = 'X-Munch-SMTP-Return-Path'

#################
# Transactional #
#################
TRANSACTIONAL = {
    'X_USER_ID_HEADER': X_USER_ID_HEADER,
    'X_MESSAGE_ID_HEADER': X_MESSAGE_ID_HEADER,
    'X_HTTP_DSN_RETURN_PATH_HEADER': X_HTTP_DSN_RETURN_PATH_HEADER,
    'X_SMTP_DSN_RETURN_PATH_HEADER': X_SMTP_DSN_RETURN_PATH_HEADER,
    'X_MAIL_BATCH_HEADER': 'X-Munch-MailBatch',
    'X_MAIL_BATCH_CATEGORY_HEADER': 'X-Munch-MailBatch-Category',
    'X_MAIL_TRACK_OPEN_HEADER': 'X-Munch-Track-Open',
    'X_MAIL_TRACK_CLICKS_HEADER': 'X-Munch-Track-Clicks',
    'X_MAIL_UNSUBSCRIBE_HEADER': 'X-Munch-Unsubscribe',
    # Set these to drop to an unprivileged user after binding the SMTP daemon
    'DROP_PRIVILEGES_USER': None,
    'DROP_PRIVILEGES_GROUP': None,
    'EDGE_EHLO_AS': None,
    # Default is 200
    'EDGE_MAX_CONN': 200,
    'EDGE_TIMEOUTS': {'data_timeout': None, 'command_timeout': None},
    'PROXYPROTO_ENABLED': False,
    'STATUS_WORKER_QUEUE': 'munch.status',
    'SMTP_SMARTHOST_TLS': None,
    'SMTP_DSN_ADDRESS': "CHANGEME <foo@munch.example.com>",
    'HEADERS_TO_REMOVE': [X_MESSAGE_ID_HEADER],
    # Where do the smarthost binds
    'SMTP_BIND_HOST': '127.0.0.1',
    'SMTP_BIND_PORT': 1025,
    'SMTP_STOP_TIMEOUT': 5,
    'QUEUE_POLICIES': [
        'slimta.policy.split.RecipientSplit',
        'slimta.policy.split.RecipientDomainSplit',
        'munch.apps.transactional.policies.queue.bounces.Check',
        'munch.apps.transactional.policies.queue.sending_domain.Check',
        'slimta.policy.headers.AddDateHeader',
        'munch.apps.transactional.policies.queue.headers.AddMessageIdHeader',
        'slimta.policy.headers.AddReceivedHeader',
        'munch.apps.transactional.policies.queue.headers.Remove',
        'munch.apps.transactional.policies.queue.recipients.Clean',
        'munch.apps.transactional.policies.queue.identifier.Add',
        'munch.apps.transactional.policies.queue.exec.Apply',
        'munch.apps.transactional.policies.queue.store_mail.Store'],
    # Status logging
    'STATUS_WEBHOOK_RETRIES': 20,
    'STATUS_WEBHOOK_RETRY_INTERVAL': 180,
    'EXEC_QUEUE_POLICIES': [],
    'EXEC_QUEUE_POLICIES_CONTEXT_BUILTINS': [],
    # Filters applied to add custom headers to emails for each recipient
    # (order matters).
    'HEADERS_FILTERS': [
        'munch.apps.abuse.contentfilters.add_google_fbl_header'],
    'HEADERS_FILTERS_PARAMS': {
        # Values used to build the Google FBL header : X:X:X:tag
        # Search base for attributes is Mail object
        # 3 values max (order matters).
        'GOOGLE_FBL_TAGS': [
            'author.organization.pk',
            'batch.identifier',
        ],
    },
}

#############
# Campaigns #
#############
CAMPAIGNS = {
    'X_USER_ID_HEADER': X_USER_ID_HEADER,
    'X_MESSAGE_ID_HEADER': X_MESSAGE_ID_HEADER,
    # Cumulated max size of a message attachments
    # Applies on the actual files sizes but keep the b64-encoded size in mind.
    # Ex: 4000000 roughly equals 5333440 (~5MB) in Base64
    'ATTACHMENT_TOTAL_MAX_SIZE': 4000000,
    # Message attachment max size (per file) in bytes
    # Applies on the actual file size, not the
    # b64-encoded size which might be larger
    'ATTACHMENT_MAX_SIZE': 2097152,
    # How many mails can we add in a single API request ?
    'MAX_BULK_EMAILS': 10000,
    # Those may be set True for debug/testing only
    # On recipients adding they are checked for
    # an existing MX record on their domain.
    # BYPASS_DNS_CHECKS=True also disable this check
    'BYPASS_RECIPIENTS_MX_CHECK': False,
    'SKIP_SPAM_CHECK': False,
    'SKIP_VIRUS_CHECK': False,
    # When to opt-out after a bounce ?
    # Syntax is a 3-uplet :
    # - a list of matchs (matches beggining of bounce code)
    # - how many bounces before optout ?
    # - in which time frame are the bounces counted ?
    'BOUNCE_POLICY': [(['4.'], 10, 30 * 6), (['5.', ''], 3, 365)],
    # Filters applied to the template provided by the organization to produce
    # the HTML template (order matters).
    'HTML_TEMPLATE_FILTERS': [
        'munch.apps.campaigns.contentfilters.css_inline_html',
        'munch.apps.hosted.contentfilters.handle_images',
        'munch.apps.campaigns.contentfilters.clean_html'],
    # Filters applied on the HTML content build for each specific recipient
    # (order matters)
    'HTML_INDIVIDUAL_FILTERS': [
        'munch.apps.optouts.contentfilters.set_unsubscribe_url',
        'munch.apps.tracking.contentfilters.add_tracking_image',
        'munch.apps.tracking.contentfilters.rewrite_html_links',
        'munch.apps.hosted.contentfilters.set_web_link_url',
        'munch.apps.campaigns.contentfilters.apply_mailmerge'],
    # Filters applied on the plain text content build for each specific
    # recipient (order matters)
    'PLAINTEXT_INDIVIDUAL_FILTERS': [
        'munch.apps.tracking.contentfilters.rewrite_plaintext_links',
        'munch.apps.optouts.contentfilters.set_unsubscribe_url',
        'munch.apps.hosted.contentfilters.set_web_link_url',
        'munch.apps.campaigns.contentfilters.apply_mailmerge'],
    # Filters applied on the HTML content built for web (browser) view
    # (order matters).
    'WEB_HTML_INDIVIDUAL_FILTERS': [
        'munch.apps.tracking.contentfilters.web_rewrite_html_links',
        'munch.apps.campaigns.contentfilters.apply_mailmerge'],
    # Filters applied to add custom headers to emails for each recipient
    # (order matters).
    'HEADERS_FILTERS': [
        'munch.apps.abuse.contentfilters.add_google_fbl_header'],
    'HEADERS_FILTERS_PARAMS': {
        # Values used to build the Google FBL header : X:X:X:tag
        # Search base for attributes is Mail object
        # 3 values max (order matters).
        'GOOGLE_FBL_TAGS': [
            'message.author.organization.pk',
            'message.identifier',
        ],
    },
}

###############
# Backmuncher #
###############
BACKMUNCHER = {
    'SMTP_BIND_HOST': 'localhost',
    'SMTP_BIND_PORT': 12525,
    'EDGE_EHLO_AS': 'localhost',
    'DROP_PRIVILEGES_USER': None,
    'DROP_PRIVILEGES_GROUP': None,
}

#########
# Users #
#########
USERS = {
    # Value of CNAME record for organizations app_domains
    'ORGANIZATION_APP_DOMAIN_CNAME': 'munch.example.com'
}

###########
# Domains #
###########
DOMAINS = {
    # Should be included in the spf line
    'SPF_INCLUDE': 'munch.example.com',
    'DKIM_KEY_ID': 'munch',
    'DKIM_KEY_CONTENT': '"v=DKIM1; k=rsa; t=y; p=CHANGEME',
    'DKIM_CNAME': 'dkim.example.com'
}

############
# Optouts #
############
UNSUBSCRIBE_PLACEHOLDER = 'UNSUBSCRIBE_URL'
OPTOUTS = {
    'UNSUBSCRIBE_PLACEHOLDER': UNSUBSCRIBE_PLACEHOLDER,
}

##########
# Hosted #
##########
WEB_LINK_PLACEHOLDER = 'WEB_VERSION_URL'
HOSTED = {
    'WEB_LINK_PLACEHOLDER': WEB_LINK_PLACEHOLDER,
}

################
# Upload store #
################
UPLOAD_STORE = {
    'URL_PREFIX': 'uploads',
    'URL': 'http://munch.example.com',
    'IMAGE_MAX_WIDTH': 600,
    'BACKEND': 'munch.apps.upload_store.backends.LocalFileSystemStorage'
}

############
# Contacts #
############
CONTACTS = {
    # How many contacts can we add in a single API request ?
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

############
# Mailsend #
############
MAILSEND = {
    # All Internal mailsend emails will be send to a blackhole
    'SANDBOX': True,
    'RELAY_TIMEOUTS': {
        'connect_timeout': 30.0, 'command_timeout': 30.0,
        'data_timeout': None, 'idle_timeout': None},
    # Timeout for MailStatus cache
    'MAILSTATUS_CACHE_TIMEOUT': 60 * 60 * 24 * 15,
    'X_POOL_HEADER': X_POOL_HEADER,
    'X_MESSAGE_ID_HEADER': X_MESSAGE_ID_HEADER,
    # Letting to None will make it use the host FQDN
    'SMTP_WORKER_EHLO_AS': 'munch.example.com',
    # Letting to None fallback to system routing
    # example: '1.2.3.4'
    'SMTP_WORKER_SRC_ADDR': None,
    # Backoff time is exponentially growing up to max_retry_interval and then
    # staying there on each retry till we reach time_before_drop.
    'RETRY_POLICY': {
        # Minimun time between two retries
        'min_retry_interval': 600,
        # Maximum time between two retries
        'max_retry_interval': 3600,
        # Time before we drop the mail and notify sender
        'time_before_drop': 2 * 24 * 3600},
    # Set this to an encoder fromhttps://docs.python.org/3.4/library/email.encoders.html#module-email.encoders  # noqa
    # to convert utf-8 emails to ascii
    'BINARY_ENCODER': None,
    'BLACKLISTED_HEADERS': [
        X_POOL_HEADER,
        X_HTTP_DSN_RETURN_PATH_HEADER,
        X_SMTP_DSN_RETURN_PATH_HEADER],
    'RELAY_POLICIES': [
        'munch.apps.transactional.policies.relay.headers.RewriteReturnPath',
        'munch_mailsend.policies.relay.headers.StripBlacklisted',
        # 'munch_mailsend.policies.relay.dkim.Sign'],
    ],
    'WORKER_POLICIES': [
        # 'munch_mailsend.policies.mx.pool.Policy',
        # 'munch_mailsend.policies.mx.rate_limit.Policy',
        # 'munch_mailsend.policies.mx.greylist.Policy',
        # 'munch_mailsend.policies.mx.warm_up.Policy',
    ],
    'WORKER_POLICIES_SETTINGS': {
        'rate_limit': {
            'domains': [
                (r'.*', 2)],
            'max_queued': 60 * 15},
        'warm_up': {
            'prioritize': 'equal',
            'domain_warm_up': {
                'matrix': [50, 100, 300, 500, 1000],
                'goal': 500,
                'max_tolerance': 10,
                'step_tolerance': 10,
                'days_watched': 10,
            },
            'ip_warm_up': {
                'matrix': [50, 100, 300, 500, 1000],
                'goal': 500,
                'max_tolerance': 10,
                'step_tolerance': 10,
                'enabled': False,
                'days_watched': 10,
            }
        },
        'pool': {'pools': ['default']},
        'greylist': {'min_retry': 60 * 5},
    },
    'WARM_UP_DOMAINS': {},
    'DKIM_PRIVATE_KEY': None,
    'DKIM_SELECTOR': None,
    'TLS': {'keyfile': None, 'certfile': None},
    'TASKS_SETTINGS': {
        'send_email': {
            'default_retry_delay': 180,
            'max_retries': (2 * 7 * 24 * 60 * 60) / 180
        },
        'route_envelope': {
            'default_retry_delay': 180,
            'max_retries': (2 * 7 * 24 * 60 * 60) / 180
        }
    }
}

#######
# API #
#######
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTOCOL', 'https')
JWT_AUTH = {
    'JWT_ALLOW_REFRESH': True,
    'JWT_PAYLOAD_HANDLER': 'munch.apps.users.jwt.jwt_payload_handler'
}
REST_FRAMEWORK = {
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1'],
    'DEFAULT_VERSIONING_CLASS': (
        'munch.core.utils.versioning.NamespaceVersioning'),
    'EXCEPTION_HANDLER': 'munch.core.utils.exceptions.exception_handler',
    'DEFAULT_PERMISSION_CLASSES': [
        'munch.core.utils.permissions.IsOwnerOrAdmin'],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'munch.apps.users.authentication.SecretBasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_jwt.authentication.JSONWebTokenAuthentication',
    ],
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
        'munch.core.utils.renderers.PaginatedCSVRenderer'
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
        'munch.core.utils.parsers.CSVParser',
    ),
    'DEFAULT_FILTER_BACKENDS': ['rest_framework.filters.DjangoFilterBackend'],
    'DEFAULT_PAGINATION_CLASS': (
        'munch.core.utils.pagination.CountedPageNumberPagination'),
    'VIEW_DESCRIPTION_FUNCTION': 'munch.core.utils.api.get_view_description',
    'TEST_REQUEST_RENDERER_CLASSES': (
        'rest_framework.renderers.MultiPartRenderer',
        'rest_framework.renderers.JSONRenderer',
        'rest_framework_csv.renderers.CSVRenderer',
    ),
}

#########
# Spamd #
#########
# host and port are resolved via DNS SRV
# Alternatively, you can define port and host (see commented lines)
# SPAMD_SERVICE_NAME = 'sa.example.munch'
SPAMD_PORT = 1783
SPAMD_HOST = 'localhost'

#########
# Clamd #
#########
# CLAMD_SERVICE_NAME = 'av.example.munch'
CLAMD_PORT = 49227
CLAMD_HOST = 'localhost'
