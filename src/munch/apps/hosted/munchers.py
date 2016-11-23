from django.conf import settings

from munch.core.mail.utils.munchers import ContentMuncherRunner

# Munchers on the content that is displayed in HTML web version
# (served via HTTP)
post_web_html_individual = ContentMuncherRunner(
    settings.CAMPAIGNS, 'WEB_HTML_INDIVIDUAL_FILTERS')
