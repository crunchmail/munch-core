import os
import json
import operator
from functools import wraps

from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import HtmlFormatter
from django.conf import settings
from django.utils.safestring import mark_safe
from django.template.loader import get_template
from django.template import TemplateDoesNotExist
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch


class NoDefaultProvided(object):
    pass


def rgetattr(obj, name, default=NoDefaultProvided):
    """
    Same as getattr(), but allows dot notation lookup
    See: http://stackoverflow.com/questions/11975781
    """

    try:
        return operator.attrgetter(name)(obj)
    except AttributeError:
        if default != NoDefaultProvided:
            return default
        raise


def template_exists(name):
    try:
        get_template(name)
        return True
    except TemplateDoesNotExist:
        return False


# We want to be able to specify two types of MUNCH_LOGIN_URL in settings:
#   - a django url, which can handle a reverse()
#   - an arbitrary string for external urls
# And since we generate password confirmations ourselves, we need this
# to properly set the context
def get_login_url():
    try:
        return reverse(settings.LOGIN_URL)
    except NoReverseMatch:
        return settings.LOGIN_URL


def get_mail_by_identifier(identifier, must_raise=True):
    from django.core.exceptions import ObjectDoesNotExist
    from munch.apps.campaigns.models import Mail as CampaignsMail
    from munch.apps.transactional.models import Mail as TransactionalMail

    if identifier.startswith('c-'):
        mail = CampaignsMail.objects.filter(identifier=identifier).first()
        if mail:
            return mail

    if identifier.startswith('t-'):
        mail = TransactionalMail.objects.filter(identifier=identifier).first()
        if mail:
            return mail

    if must_raise:
        raise ObjectDoesNotExist(
            'No Mail (campaigns.Mail, transactional.Mail) '
            'with identifier "{}".'.format(identifier))


def pretty_json_as_html(data, sort_keys=True):
    response = json.dumps(data, sort_keys=sort_keys, indent=2)
    # Truncate the data. Alter as needed
    response = response[:5000]

    # Get the Pygments formatter
    formatter = HtmlFormatter(style='colorful')

    # Highlight the data
    response = highlight(response, JsonLexer(), formatter)

    # Get the stylesheet
    style = "<style>" + formatter.get_style_defs() + "</style><br>"
    # Safe the output
    return mark_safe(style + response)


get_worker_types = lambda: [v.lower() for v in os.environ.get(
    'WORKER_TYPE', 'all').split(',')]
available_worker_types = ['all', 'core', 'status', 'gc']


def monkey_patch_slimta_exception():
    from django.conf import settings

    if hasattr(settings, 'RAVEN_CONFIG'):
        import logging

        import slimta.logging  # noqa

        def log_sentry_exception(name, **kwargs):
            logger = logging.getLogger(name)
            logger.error('Unhandled exception', exc_info=True)

        def logline(log, type, typeid, operation, **data):
            if not data:
                log('{0}:{1}:{2}'.format(
                    type, typeid, operation), exc_info=True)
            else:
                data_str = ' '.join(
                    ['='.join((key, slimta.logging.log_repr.repr(val)))
                        for key, val in sorted(data.items())])
                log('{0}:{1}:{2} {3}'.format(
                    type, typeid, operation, data_str), exc_info=True)

        slimta.logging.log_exception = log_sentry_exception
        slimta.logging.logline = logline
        slimta.logging.socket_error_log_level = logging.WARNING


def save_timer(name):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if settings.STATSD_ENABLED:
                from statsd.defaults.django import statsd
                timer = statsd.timer(name)
                timer.start()
            result = f(*args, **kwargs)
            if settings.STATSD_ENABLED:
                timer.stop()
            return result
        return wrapper
    return decorator
