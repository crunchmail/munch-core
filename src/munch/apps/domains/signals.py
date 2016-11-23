import logging

from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import pre_save
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from munch.apps.campaigns.models import Message

from .utils import SPFValidator
from .models import SendingDomain


log = logging.getLogger(__name__)


@receiver(pre_save, sender=Message)
def validate_from_domain(sender, instance, raw, *args, **kwargs):
    if raw:
        return

    if settings.BYPASS_DNS_CHECKS:
        log.debug(
            'Bypassing dns checks because it '
            'settings "BYPASS_DNS_CHECKS" is enabled.')
        return

    if instance.pk:
        previous = Message.objects.only('sender_email').get(pk=instance.id)
        if previous.sender_email == instance.sender_email:
            log.info(
                'Bypassing dns checks because '
                '"Message.sender_email" has not changed.')
            return

    message = instance
    try:
        all_domains = SendingDomain.objects
        org_id = message.get_organization()
        qs = all_domains.filter(organization=org_id) | all_domains.filter(
            alt_organizations__in=[org_id])
        organization_domains = qs.distinct()
        domain = organization_domains.get_from_email_addr(message.sender_email)
    except SendingDomain.DoesNotExist:
        raise ValidationError(_(
            'You must add and configure "{}" domain'.format(
                message.sender_email)))
    if not domain.is_valid():
        raise ValidationError(_(
            'Sending domain invalid, please verify '
            'DNS configuration ({})'.format(domain.name)))


@receiver(pre_save, sender=Message)
def validate_envelope_domain(sender, instance, raw, *args, **kwargs):
    if raw or settings.BYPASS_DNS_CHECKS:
        return
    if instance.status == Message.SENDING:
        previous = Message.objects.only('status').get(pk=instance.pk)
        if previous.status != Message.SENDING:
            validator = SPFValidator(
                spf_include=settings.DOMAINS['SPF_INCLUDE'])
            validator.validate(settings.RETURNPATH_DOMAIN)
