from django.conf import settings

from munch.core.mail.utils.munchers import ContentMuncherRunner
from munch.core.mail.utils.munchers import HeadersMuncherRunner

# Filters definitions
post_individual_html_generation = ContentMuncherRunner(
    settings.CAMPAIGNS, 'HTML_INDIVIDUAL_FILTERS')
post_template_html_generation = ContentMuncherRunner(
    settings.CAMPAIGNS, 'HTML_TEMPLATE_FILTERS')
post_individual_plaintext_generation = ContentMuncherRunner(
    settings.CAMPAIGNS, 'PLAINTEXT_INDIVIDUAL_FILTERS')
post_headers_generation = HeadersMuncherRunner(
    settings.CAMPAIGNS, 'HEADERS_FILTERS')
