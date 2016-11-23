import logging

import dns
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from munch.apps.users.models import Organization
from munch.core.mail.utils import extract_domain
from munch.core.utils.models import AbstractOwnedModel
from munch.core.utils.managers import OwnedModelQuerySet
from munch.core.utils.validators import DomainNameValidator
from .fields import DomainCheckField

log = logging.getLogger('munch')


class SendingDomainQueryset(OwnedModelQuerySet):
    def get_from_email_addr(self, email_addr, must_raise=True):
        domain = extract_domain(email_addr)
        if must_raise:
            return self.get(name=domain)
        return self.filter(name=domain).first()


class SendingDomain(AbstractOwnedModel):
    name = models.CharField(
        verbose_name=_('name'), max_length=200,
        validators=[DomainNameValidator()])
    creation_date = models.DateTimeField(default=timezone.now)
    update_date = models.DateTimeField(blank=True)
    organization = models.ForeignKey(
        Organization, related_name='domains', verbose_name=_('organization'))
    alt_organizations = models.ManyToManyField(Organization, blank=True)
    dkim_status = DomainCheckField(verbose_name=_('DKIM status'))
    dkim_status_date = models.DateTimeField(
        verbose_name=_('DKIM status last change'), blank=True, null=True)

    app_domain = models.CharField(
        _('Custom application domain'), max_length=200,
        blank=True, default='', help_text=_(
            'Domain to use for email links generation'),
        validators=[DomainNameValidator()])
    app_domain_status = DomainCheckField(
        verbose_name=_('Custom application domain status'))
    app_domain_status_date = models.DateTimeField(
        verbose_name=_('Custom application domain status last change'),
        blank=True, null=True)

    objects = SendingDomainQueryset.as_manager()

    owner_path = 'organization'
    author_path = AbstractOwnedModel.IRRELEVANT

    class Meta(AbstractOwnedModel.Meta):
        unique_together = (('name', 'organization'),)
        verbose_name = _("sending domain")
        verbose_name_plural = _("sending domains")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from .tasks import validate_sending_domain_field

        created = not self.pk
        if not created:
            previous = SendingDomain.objects.get(pk=self.pk)

        # Set changed fields to "Pending" or "Unknown"
        if created or previous.name != self.name:
            self.dkim_status = DomainCheckField.PENDING

        if self.app_domain:
            if created or previous.app_domain != self.app_domain:
                self.app_domain_status = DomainCheckField.PENDING
        else:
            if not created and previous.app_domain != self.app_domain:
                self.app_domain_status = DomainCheckField.UNKNOWN

        self.update_date = timezone.now()

        super().save(*args, **kwargs)

        if created:
            validate_sending_domain_field.apply_async([self.id, 'dkim'])
            if self.app_domain:
                validate_sending_domain_field.apply_async(
                    [self.id, 'app_domain'])
        else:
            if self.app_domain and (previous.app_domain != self.app_domain):
                validate_sending_domain_field.apply_async(
                    [self.id, 'app_domain'])

    def validate_app_domain(self):
        if self.app_domain:
            log.debug('Validating SendingDomain app domain {} (pk:{})'.format(
                self.app_domain, self.pk))
            try:
                # a CNAME record should be unique
                # we also have to strip the trailing dot
                res = dns.resolver.query(
                    self.app_domain, 'CNAME')[0].to_text().strip('.')
            except (IndexError, dns.exception.DNSException):
                log.debug(
                    'No DNS answer for SendingDomain app '
                    'domain {} (pk:{})'.format(self.app_domain, self.pk))
                self.app_domain_status = DomainCheckField.NOT_CONFIGURED
            else:
                if (res == settings.USERS['ORGANIZATION_APP_DOMAIN_CNAME']):
                    log.debug(
                        'SendingDomain app domain {} correctly '
                        'configured (pk:{})'.format(self.app_domain, self.pk))
                    self.app_domain_status = DomainCheckField.OK
                else:
                    log.debug(
                        'SendingDomain app domain {} badly '
                        'configured (pk:{}) -> DNS record value: '.format(
                            self.app_domain, self.pk, res))
                    self.app_domain_status = DomainCheckField.BADLY_CONFIGURED

        return self.app_domain_status

    def validate_dkim(self):
        keydomain = '{}._domainkey.{}'.format(
            settings.DOMAINS['DKIM_KEY_ID'], self.name)
        try:
            # a CNAME record should be unique
            # we also have to strip the trailing dot
            res = dns.resolver.query(
                keydomain, 'CNAME')[0].to_text().strip('.')
        except (IndexError, dns.exception.DNSException):
            #
            # TODO: remove this when all current domains are migrated to CNAME
            # and simply fail with NOT_CONFIGURED
            #
            # Try to look for a standard TXT record
            try:
                # its not supposed to have several TXT records with same key
                res = dns.resolver.query(keydomain, 'TXT')[0].to_text()
            except (IndexError, dns.exception.DNSException):
                log.debug(
                    'No DNS answer for SendingDomain DKIM '
                    'record {} (pk:{})'.format(keydomain, self.pk))
                self.dkim_status = DomainCheckField.NOT_CONFIGURED
            else:
                if res == settings.DOMAINS['DKIM_KEY_CONTENT']:
                    log.debug(
                        'SendingDomain DKIM record {} correctly '
                        'configured (pk:{})'.format(keydomain, self.pk))
                    self.dkim_status = DomainCheckField.OK
                else:
                    log.debug(
                        'SendingDomain DKIM record {} badly '
                        'configured (pk:{}) -> DNS record value: {}'.format(
                            keydomain, self.pk, res))
                    self.dkim_status = DomainCheckField.BADLY_CONFIGURED
        else:
            if res == settings.DOMAINS['DKIM_CNAME']:
                log.debug(
                    'SendingDomain DKIM record {} correctly '
                    'configured (pk:{})'.format(keydomain, self.pk))
                self.dkim_status = DomainCheckField.OK
            else:
                log.debug(
                    'SendingDomain DKIM record {} badly '
                    'configured (pk:{}) -> DNS record value: {}'.format(
                        keydomain, self.pk, res))
                self.dkim_status = DomainCheckField.BADLY_CONFIGURED

        return self.dkim_status

    def is_valid(self):
        if self.dkim_status != DomainCheckField.OK:
            return False
        if self.app_domain and self.app_domain_status != DomainCheckField.OK:
            return False
        return True
