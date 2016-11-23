import re
from email.utils import parseaddr

import dns
import dns.exception
import dns.resolver
import clamd
from django.conf import settings
from django.core.cache import cache
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

slug_regex = re.compile(r'^[a-z-]*$')
slug_regex_validator = RegexValidator(
    regex=slug_regex.pattern,
    message='source should be composed of lowercase letters and dashes')


def validate_existing_mail_domain(email):
    """ Just checks that the associated domain of an email has an MX record.
    """
    if settings.CAMPAIGNS['BYPASS_RECIPIENTS_MX_CHECK']:
        return
    domain = parseaddr(email)[1]

    if domain is None:
        # Trigger no error because email format is supposed to be checked
        # by another validator, needless to report it a second time
        return

    else:
        key = 'domcheck:{}'.format(domain)
        has_error = cache.get(key, None)

        if has_error is None:  # Not present in cache
            try:
                dns.resolver.query(domain, 'MX')
                has_error = False
            except dns.exception.DNSException:
                has_error = True
            finally:
                cache.set(key, has_error, 60)

        if has_error:
            raise ValidationError(_(
                'This domain "{}" doesn\'t seems to be '
                'configured to received emails').format(domain))


def validate_no_virus(afile):
    """ Checks a file field against a remote antivirus service
    """
    if not settings.CAMPAIGNS['SKIP_VIRUS_CHECK']:
        try:
            host, port = settings.CLAMD_HOST, settings.CLAMD_PORT
        except AttributeError:
            results = dns.resolver.query(settings.CLAMD_SERVICE_NAME, 'SRV')
            servers = [(rr.target.to_text(True), rr.port) for rr in results]
            host, port = servers[0]

        cd = clamd.ClamdNetworkSocket(host=host, port=port)
        check_result, check_msg = cd.instream(afile)['stream']
        # example virus result
        # {'stream': ('FOUND', 'Eicar-Test-Signature')}
        if check_result == 'FOUND':
            raise ValidationError(_(
                'File contains virus: "{}"').format(check_msg))
    return afile
