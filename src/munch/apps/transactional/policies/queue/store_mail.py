import email

from django.conf import settings
from django.db import transaction
from slimta.policy import QueuePolicy
from slimta.relay import PermanentRelayError

from munch.core.mail.models import RawMail
from munch.core.mail.utils import get_app_url
from munch.core.mail.utils import extract_domain
from munch.apps.campaigns.models import Category
from munch.apps.tracking.utils import get_msg_links
from munch.apps.optouts.contentfilters import set_unsubscribe_url
from munch.apps.tracking.contentfilters import add_tracking_image
from munch.apps.tracking.contentfilters import rewrite_html_links

from ...models import Mail
from ...models import MailBatch
from ...models import MailStatus


class Store(QueuePolicy):
    """
    Should occur after a n eventual return-path rewrite,
    as data is return-path-indexed.
    """

    @transaction.atomic()
    def apply(self, envelope):
        identifier = envelope.headers.get(
            settings.TRANSACTIONAL['X_MESSAGE_ID_HEADER'])
        if not identifier or not envelope.client.get('auth'):
            # FIXME: log exact error
            raise PermanentRelayError('Internal application error')

        # Process mail content
        munchers_kwargs = {
            'mail_identifier': identifier,
            'app_url': get_app_url(
                domain=envelope.sending_domain,
                organization=envelope.organization),
        }

        msg_links = {}
        mail_kwargs = {}
        track_open = envelope.headers.get(
            settings.TRANSACTIONAL.get('X_MAIL_TRACK_OPEN_HEADER', None))
        track_open_done = False
        if track_open:
            munchers_kwargs.update({'track_open': True})
            mail_kwargs.update({'track_open': True})

        track_clicks = envelope.headers.get(
            settings.TRANSACTIONAL.get('X_MAIL_TRACK_CLICKS_HEADER', None))
        if track_clicks:
            mail_kwargs.update({'track_clicks': True})
            munchers_kwargs.update({'track_clicks': True})

        add_unsubscribe = envelope.headers.get(
            settings.TRANSACTIONAL.get('X_MAIL_UNSUBSCRIBE_HEADER', None))
        if add_unsubscribe:
            munchers_kwargs.update({
                'unsubscribe_url': Mail.unsubscribe_url(
                    identifier, envelope.user, envelope.sending_domain)})

        # Retrieve full html to extract links
        html = ''
        message = email.message_from_bytes(b'\n'.join(envelope.flatten()))
        for part in message.walk():
            if part.get_content_type() == 'text/html':
                html += part.get_payload()

        msg_links = get_msg_links(html)
        mail_kwargs.update({'msg_links': msg_links})
        munchers_kwargs.update({'links_map': msg_links})

        # Walk throught every parts to apply munchers on it
        for part in message.walk():
            if part.get_content_type() == 'text/html':
                html = part.get_payload()
                if track_open and not track_open_done:
                    html = add_tracking_image(html, **munchers_kwargs)
                    track_open_done = True
                if track_clicks:
                    html = rewrite_html_links(html, **munchers_kwargs)
                part.set_payload(html)

            content = part.get_payload()

            if add_unsubscribe:
                content = set_unsubscribe_url(content, **munchers_kwargs)

            part.set_payload(content)

        envelope.parse_msg(message)

        batch = envelope.headers.get(
            settings.TRANSACTIONAL.get('X_MAIL_BATCH_HEADER', None))
        if batch:
            batch, created = MailBatch.objects.get_or_create(
                name=batch, author=envelope.user,
                defaults={'msg_links': msg_links})
            if not created:
                batch.msg_links = msg_links
                batch.save()
            category = envelope.headers.get(
                settings.TRANSACTIONAL.get(
                    'X_MAIL_BATCH_CATEGORY_HEADER', None))
            if category:
                category, _ = Category.objects.get_or_create(
                    author=envelope.user, name=category)
                batch.category = category
                batch.save()

        raw_mail, _ = RawMail.objects.get_or_create(content=envelope.message)
        mail = Mail.objects.create(
            author=envelope.user,
            batch=batch,
            identifier=envelope.headers.get(
                settings.TRANSACTIONAL['X_MESSAGE_ID_HEADER']),
            headers={k: v.encode(
                'utf-8', 'surrogateescape').decode('utf-8') for k, v in
                envelope.headers.raw_items()},
            message=raw_mail, sender=envelope.sender,
            recipient=envelope.recipients[0],
            **mail_kwargs)
        MailStatus.objects.create(
            mail=mail,
            destination_domain=extract_domain(envelope.recipients[0]))
