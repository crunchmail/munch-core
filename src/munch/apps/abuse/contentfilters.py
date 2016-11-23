from django.conf import settings

from munch.core.utils import rgetattr
from munch.core.mail.utils.parsers import extract_domain


def add_google_fbl_header(headers, mail, filters_settings):
    if headers and mail and filters_settings:
        if extract_domain(mail.recipient) == 'gmail.com':
            gtags = []
            for s in filters_settings['GOOGLE_FBL_TAGS'][:3]:
                attr = rgetattr(mail, s, None)
                if attr:
                    gtags.append(str(attr))
            if gtags:
                val = '{}:{}'.format(
                    (':').join(gtags),
                    settings.GOOGLE_FBL_SENDER_ID
                )
            else:
                val = settings.GOOGLE_FBL_SENDER_ID
            headers.update({'Feedback-ID': val})
