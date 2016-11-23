from abc import ABC

import django.core.mail.message
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from munch.core.utils import template_exists
from munch.apps.campaigns.contentfilters import css_inline_html

from . import mk_msgid


class ApplicationMessage(ABC):

    def __init__(self, to, subject, template, render_context={}):

        if not isinstance(to, list):
            to = [to]

        render_context.update({'application_message_recipient': to[0]})
        self.render_context = render_context
        body = render_to_string(template, render_context)

        # Use max line length from RFC2822 (78) instead of RFC5322 (998)
        # to force conversion to quoted-printable in almost all cases
        django.core.mail.message.RFC5322_EMAIL_LINE_LENGTH_LIMIT = 78

        self.msg = EmailMultiAlternatives(
            subject=subject, body=body, to=to, from_email=self.message_from,
            headers={
                'Auto-Submitted': 'auto-generated',
                'Return-Path': settings.SERVICE_MSG_RETURN_PATH,
                'Message-ID': mk_msgid()
            },
        )

    def add_html_part_if_exists(self, template, render_context=None):
        if render_context is None:
            render_context = self.render_context

        if template_exists(template):
            html = render_to_string(template, render_context)
            content = css_inline_html(html)
            self.msg.attach_alternative(content, 'text/html')

    def send(self):
        self.msg.send()


class ServiceMessage(ApplicationMessage):

    def __init__(self, *args, **kwargs):
        self.message_from = '{} <{}>'.format(
            settings.SERVICE_MSG_FROM_NAME, settings.SERVICE_MSG_FROM_EMAIL)
        super().__init__(*args, **kwargs)


class NotificationMessage(ApplicationMessage):

    def __init__(self, *args, **kwargs):
        self.message_from = '{} <{}>'.format(
            settings.NOTIFICATION_MSG_FROM_NAME,
            settings.NOTIFICATION_MSG_FROM_EMAIL)
        super().__init__(*args, **kwargs)
        if settings.NOTIFICATION_MSG_FROM_EMAIL != settings.SERVICE_MSG_FROM_EMAIL:  # noqa
            self.msg.extra_headers.update({
                'Reply-To': settings.SERVICE_MSG_FROM_EMAIL})
