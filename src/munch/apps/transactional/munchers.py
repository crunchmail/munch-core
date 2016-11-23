from django.conf import settings

from munch.core.mail.utils.munchers import HeadersMuncherRunner


# Filters definition
headers_filters = HeadersMuncherRunner(
    settings.TRANSACTIONAL, 'HEADERS_FILTERS')
