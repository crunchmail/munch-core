from urllib.parse import urljoin

from django.urls import reverse
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from munch.core.mail.utils import get_app_url


class PolicyBackend:
    def apply(self, item, policies_list):
        raise NotImplementedError()


class DoubleOptIn(PolicyBackend):
    def apply(self, item, policies_list):
        subscription_url = get_app_url(organization=item.get_owner())

        if 'BounceCheck' in policies_list:
            return_path = 'subscription-bounce+{uuid}@{fqdn}'.format(
                uuid=item.uuid, fqdn=settings.RETURNPATH_DOMAIN)
        else:
            return_path = settings.SERVICE_MSG_FROM_EMAIL
        confirmation_link = urljoin(
            subscription_url,
            reverse('confirmation', kwargs={'uuid': item.uuid}))
        message = EmailMessage(
            subject='Votre inscription',
            body=render_to_string(
                'contacts/double_opt_in_confirmation.txt',
                {'contact': item, 'confirmation_link': confirmation_link}),
            to=(item.address, ),
            from_email='{} <{}>'.format(
                settings.SERVICE_MSG_FROM_NAME,
                settings.SERVICE_MSG_FROM_EMAIL),
            headers={
                'Auto-Submitted': 'auto-generated',
                'Return-Path': return_path})
        message.send()


class BounceCheck(PolicyBackend):
    def apply(self, item, policies_list):
        # if double opt-in is set up, we use the validation mail to check
        # bounce
        if 'DoubleOptIn' not in policies_list:
            return_path = 'subscription-bounce+{uuid}@{fqdn}'.format(
                uuid=item.uuid, fqdn=settings.RETURNPATH_DOMAIN)
            message = EmailMessage(
                subject='Votre inscription',
                body=render_to_string(
                    'contacts/bounce_check_confirmation.txt',
                    {'contact': item}),
                to=(item.address, ),
                from_email='{} <{}>'.format(
                    settings.SERVICE_MSG_FROM_NAME,
                    settings.SERVICE_MSG_FROM_EMAIL),
                headers={
                    'Auto-Submitted': 'auto-generated',
                    'Return-Path': return_path})
            message.send()
