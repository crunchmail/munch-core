import re

import dns
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

# Regexp matching valid SPF record
r_spf = re.compile(r'"v=spf1 .*[\?\-~]all"')


class SPFValidator:
    """ Just a tool to validate SPF records
    """

    def __init__(self, spf_include):
        """
        :param spf_include: a domain that should be spf-included
                            for the record to be good.
        """
        self.spf_include = spf_include

    def _fetch_spf_record(self, domain_name):
        """ Looks for SPF record in all TXT and SPF records

        :return the first valid SPF field value found or None
        """
        for field in ('TXT', 'SPF'):
            try:
                res = dns.resolver.query(domain_name, field)
            except dns.exception.DNSException:
                # try next record type
                pass
            else:
                for field in res:
                    field_text = field.to_text()
                    if r_spf.match(field_text):
                        return field_text

    def validate(self, domain_name):
        include = 'include:{}'.format(self.spf_include)
        field_text = self._fetch_spf_record(domain_name)
        if field_text is None:
            raise ValidationError(
                _("SPF not configured for {} domain").format(domain_name))
        if include in field_text:
            return domain_name
        else:
            raise ValidationError(_(
                "SPF badly configured for {} domain").format(domain_name))
