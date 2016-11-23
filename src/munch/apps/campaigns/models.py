import html
import email
import magic
import urllib
import logging
import re
from os.path import join
from base64 import b64encode

import chardet
import html2text
import lxml.html
import lxml.etree
import celery
import django.core.mail.message
from django.conf import settings
from django.db import models
from django.db import transaction
from django.utils import timezone
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.contrib.postgres.fields import JSONField
from django.contrib.postgres.fields import HStoreField
from django.template.loader import render_to_string
from django_fsm import transition
from slimta.envelope import Envelope

from munch.core.models import Category
from munch.core.mail.backend import Backend
from munch.core.utils import save_timer
from munch.core.utils.models import AbstractOwnedModel
from munch.core.mail.utils import mk_base64_uuid
from munch.core.mail.utils import mk_msgid
from munch.core.mail.utils.emails import NotificationMessage
from munch.core.mail.models import AbstractMail
from munch.core.mail.models import AbstractMailStatus
from munch.core.mail.models import BaseMailStatusManager
from munch.core.models import ValidationSignalsModel
from munch.apps.spamcheck import SpamResult
from munch.apps.spamcheck import SpamChecker
from munch.apps.spamcheck import SpamCheckerError
from munch.apps.domains.models import SendingDomain
from munch.apps.users.models import MunchUser
from munch.apps.optouts.models import OptOut
from munch.apps.tracking.utils import WebKey
from munch.apps.tracking.utils import get_msg_links
from munch.apps.tracking.models import TrackRecord
from munch.apps.tracking.models import READ_BROWSER

from .fields import FSMAutoField
from .validators import slug_regex_validator
from .exceptions import WrongHTML
from .managers import MailManager
from .managers import MailQuerySet

from .managers import MailStatusQuerySet
from .munchers import post_template_html_generation
from .munchers import post_individual_html_generation
from .munchers import post_individual_plaintext_generation
from .munchers import post_headers_generation

log = logging.getLogger('munch')

email.charset.add_charset('utf-8', email.charset.SHORTEST, None, 'utf-8')


class MailStatus(AbstractOwnedModel, AbstractMailStatus):
    mail = models.ForeignKey(
        'Mail', related_name='statuses', verbose_name=_('mail'))

    objects = BaseMailStatusManager.from_queryset(MailStatusQuerySet)()

    class Meta(AbstractOwnedModel.Meta):
        verbose_name = _('email status')
        verbose_name_plural = _('email statuses')
        get_latest_by = 'creation_date'

    owner_path = 'mail__message__author__organization'
    author_path = 'mail__message__author'

    def __str__(self):
        return _('Message {} is {}').format(self.mail.identifier, self.status)

    def get_organization(self):
        return self.mail.message.author.organization

    def update_message_status(self):
        try:
            if self.mail.curstatus in MailStatus.FINAL_STATES:
                # If there is nothing left to send,
                # change the state of the message !
                if self.mail.message.status == Message.SENDING:
                    remaining = self.mail.message.mails.legit_for(
                        self.mail.message).pending().count()
                    if remaining == 0:
                        self.mail.message.status = Message.SENT
                        self.mail.message.save()
        except Mail.DoesNotExist:
            pass

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_message_status()


class TolerantForeignKey(models.ForeignKey):
    """ A ForeignKey which can point to an unsaved object

    It's back to django >= 1.7 behaviour
    to allow mem-only message making
    """
    allow_unsaved_instance_assignment = True


def get_base_mail_identifier():
    return mk_base64_uuid('c-')


class BaseMail(AbstractOwnedModel, AbstractMail):
    identifier = models.CharField(
        max_length=35, db_index=True, unique=True,
        default=get_base_mail_identifier, verbose_name=_('identifier'))
    message = TolerantForeignKey(
        'Message', related_name='%(class)ss', verbose_name=_('message'))
    properties = HStoreField(
        null=True, blank=True, verbose_name=_('properties'))
    source_type = models.CharField(
        blank=True, max_length=100,
        validators=[slug_regex_validator], verbose_name=_('source type'))
    source_ref = models.CharField(
        blank=True, max_length=200, verbose_name=_('source reference'))
    # curstatus is overwritten because we want FSMAutoField here
    curstatus = FSMAutoField(
        default=AbstractMailStatus.UNKNOWN,
        choices=AbstractMailStatus._meta.get_field('status').choices,
        verbose_name=_('current status'))

    class Meta(AbstractOwnedModel.Meta):
        abstract = True

    owner_path = 'message__author__organization'
    author_path = 'message__author'

    def __str__(self):
        return _('Message {} to {}').format(self.identifier, self.recipient)

    def get_organization(self):
        return self.message.author.organization

    def get_category(self):
        if self.message.category:
            return self.message.category

    def get_related_optout(self):
        """ Gets the related OptOut

        That is not an optout on that email, but rather an optout on another
        email to the same recipient.

        :returns: an OptOut object or None
        """
        if self.message.category:
            qs = OptOut.objects.filter(category=self.message.category)
        else:
            qs = OptOut.objects.filter(
                author__organization=self.message.author.organization)

        return qs.for_email(self.recipient)

    @property
    def abuse_url(self):
        relative_url = reverse(
            'abuse-report', kwargs={'identifier': self.identifier})
        return urllib.parse.urljoin(self.message.get_app_url(), relative_url)

    @property
    def unsubscribe_url(self):
        relative_url = reverse(
            'unsubscribe', kwargs={'identifier': self.identifier})
        return urllib.parse.urljoin(self.message.get_app_url(), relative_url)

    @property
    def web_view_url(self):
        relative_url = reverse(
            'message_web_view', kwargs={'identifier': self.message.identifier})

        abs_url = urllib.parse.urljoin(
            self.message.get_app_url(), relative_url)

        if self.message.track_open:
            return abs_url + '?web_key={}'.format(
                WebKey.from_instance(self.identifier).token)
        else:
            return abs_url

    def as_message(self, with_body=True):
        return self.message.to_mail(self, with_body=with_body)

    def get_headers(self):
        message = self.as_message(with_body=False).message()
        return dict(message)

    def as_envelope(self):
        message = self.as_message()
        envelope = Envelope()
        envelope.parse(message.message().as_bytes())
        envelope.sender = message.from_email
        envelope.recipients.append(self.recipient)
        return envelope

    def get_original_links(self, links):
        original_links = {}
        for link in links:
            original_links[link] = self.message.msg_links.get(link)
        return original_links

    def last_status(self):
        try:
            # Try to use cached version, see api/views.py
            return self.last_status_cached[0]
        except IndexError:
            return None
        except AttributeError:
            try:
                return self.statuses.latest()
            except MailStatus.DoesNotExist:
                return None

    last_status.short_description = _('Last status')

    def is_delivered(self):
        return self.curstatus == 'delivered'

    @transition(field=curstatus,
                source=MailStatus.UNKNOWN, target=MailStatus.QUEUED)
    def celery_enqueued(self):
        pass

    @transition(field=curstatus,
                source=MailStatus.UNKNOWN, target=MailStatus.IGNORED)
    def ignoring_send(self):
        pass

    @transition(field=curstatus,
                source=MailStatus.QUEUED, target=MailStatus.IGNORED)
    def delivery_will_fail(self):
        pass

    @transition(field=curstatus,
                source=MailStatus.QUEUED, target=MailStatus.SENDING)
    def sending_begin(self):
        pass

    @transition(field=curstatus,
                source=MailStatus.SENDING, target=MailStatus.DELAYED)
    def delayed_dsn(self):
        pass

    @transition(field=curstatus,
                source=MailStatus.DELAYED, target=MailStatus.DELIVERED)
    def reception_after_delay(self):
        pass

    @transition(field=curstatus,
                source=MailStatus.DELAYED, target=MailStatus.BOUNCED)
    def hardbounce_after_delay(self):
        pass

    @transition(field=curstatus,
                source=MailStatus.DELAYED, target=MailStatus.DROPPED)
    def softbounce_after_delay(self):
        pass

    @transition(field=curstatus,
                source=MailStatus.DELAYED, target=MailStatus.SENDING)
    def sending_after_delay(self):
        pass

    @transition(field=curstatus,
                source=MailStatus.SENDING, target=MailStatus.DELIVERED)
    def mx_reception(self):
        pass

    @transition(field=curstatus,
                source=MailStatus.SENDING, target=MailStatus.BOUNCED)
    def mx_hardbounce(self):
        pass

    @transition(field=curstatus,
                source=MailStatus.SENDING, target=MailStatus.DROPPED)
    def mx_softbounce(self):
        pass

    @transition(field=curstatus,
                source=MailStatus.DELIVERED, target=MailStatus.BOUNCED)
    def hardbounce_backscatter(self):
        """May happen : local MTA ack, then remote mta backscatters
        """
        pass

    @transition(field=curstatus,
                source=MailStatus.DELIVERED, target=MailStatus.DROPPED)
    def softbounce_backscatter(self):
        """May happen : local MTA ack, then remote mta backscatters
        """
        pass


class Mail(BaseMail):
    objects = MailManager.from_queryset(MailQuerySet)()

    class Meta:
        unique_together = [('recipient', 'message')]


class Message(ValidationSignalsModel, AbstractOwnedModel):
    NEW = 'new'
    MSG_OK = 'message_ok'
    MSG_ISSUES = 'message_issues'
    SENDING = 'sending'
    SENT = 'sent'
    STATUS_CHOICES = (
        (NEW, _('Created')),
        (MSG_OK, _('Message approved')),
        (MSG_ISSUES, _('Message contains issues')),
        (SENDING, _('Sending')),
        (SENT, _('Sent')))

    # Identifier is used as a key for public URLs.
    identifier = models.CharField(
        max_length=35, db_index=True, unique=True, editable=False,
        default=mk_base64_uuid, verbose_name=_('identifier'))

    # User filled
    name = models.CharField(_('name'), max_length=60)

    # Message-related fields (user-filled)
    sender_email = models.EmailField(_('sender address'))
    sender_name = models.CharField(_('sender name'), max_length=50)

    subject = models.CharField(_('subject'), blank=True, max_length=130)
    html = models.TextField(blank=True)

    # Auto-filled at first save
    status = FSMAutoField(_('status'), default=NEW, choices=STATUS_CHOICES)

    author = models.ForeignKey(MunchUser, verbose_name=_('author'))

    creation_date = models.DateTimeField(
        _('creation date'), auto_now_add=True, help_text=_('automatic'))
    send_date = models.DateTimeField(_('send date'), null=True, blank=True)
    completion_date = models.DateTimeField(
        _("complete sent date"), null=True, blank=True)

    # Optional category
    category = models.ForeignKey(
        Category, null=True, blank=True,
        related_name='messages',
        verbose_name=_('category'))

    # Opaque Hash to be used by API clients to store whatever they fancy
    properties = HStoreField(
        verbose_name=_('properties'), null=True, blank=True)

    # Settings
    external_optout = models.BooleanField(
        _('external optout'), default=False, help_text=(
            _(
                "If enabled, this message, instead of optout form, recipients "
                "will be invited to contact you.")))
    detach_images = models.BooleanField(
        _('host images'), default=False,
        help_text=_(
            "Host linked images on our servers instead of original links."))
    track_open = models.BooleanField(
        _('track opens'), default=False,
        help_text=(_("Detect who opens message by adding hidden image.")))
    track_clicks = models.BooleanField(
        _('track clicks'), default=False,
        help_text=_(
            "Detect which links were clicked by replacing "
            "original links by redirections"))

    # Auto-filled (message related)
    spam_score = models.FloatField(
        blank=True, null=True, verbose_name=_('spam score'))
    spam_details = JSONField(
        null=True, blank=True, verbose_name=_('Triggered anti-spam rules'))
    is_spam = models.BooleanField(_('Detected as spam'), default=False)
    spam_check_error = models.TextField(
        null=True, blank=True, verbose_name=_('Spam check error'))
    msg_issue = models.CharField(
        verbose_name=_('message issue'), max_length=300, blank=True, null=True)
    msg_links = HStoreField(
        verbose_name=_('message links'), null=True, blank=True)

    class Meta(AbstractOwnedModel.Meta):
        verbose_name = _('message')
        verbose_name_plural = _('messages')
        default_permissions = AbstractOwnedModel.Meta.default_permissions + (
            'previewsend_organizations', 'previewsend_mine', 'previewsend')

    owner_path = 'author__organization'
    author_path = 'author'

    def __str__(self):
        return self.name

    def get_organization(self):
        return self.author.organization

    def get_sending_domain(self):
        all_domains = SendingDomain.objects
        org_id = self.get_organization()
        qs = all_domains.filter(organization=org_id) | all_domains.filter(
            alt_organizations__in=[org_id])
        organization_domains = qs.distinct()
        return organization_domains.get_from_email_addr(
            self.sender_email, must_raise=False)

    def get_app_url(self):
        from munch.core.mail.utils import get_app_url

        return get_app_url(
            domain=self.get_sending_domain(),
            organization=self.get_organization())

    def willsend_addresses(self):
        return self.mails.legit_for(self).values_list('recipient', flat=True)

    def willnotsend_addresses(self):
        return self.mails.not_legit_for(self).values_list(
            'recipient', flat=True)

    def get_clicks_defaults(self):
        if self.msg_links:
            return {k: 0 for k in list(self.msg_links.values())}
        return {}

    def get_clicks_count(self, click_qs, unique=False):
        clicked = click_qs.count_by_url(
            self.msg_links, include_any=unique, unique=unique)
        links = self.get_clicks_defaults()
        links.update(clicked)
        return links

    @save_timer(name='campaigns.Message.mk_stats')
    def mk_stats(self):
        mail_qs = self.mails.all()
        identifiers = self.mails.all().values_list('identifier', flat=True)
        click_qs = TrackRecord.objects.filter(
            identifier__in=identifiers, kind='click')
        open_qs = TrackRecord.objects.filter(
            identifier__in=identifiers, kind='read').order_by(
            'identifier', 'creation_date')
        browser_views = open_qs.filter(
            properties__source=READ_BROWSER).distinct().count()
        optout_qs = OptOut.objects.filter(
            identifier__in=self.mails.values_list('identifier', flat=True))

        open_time_serie = [int(p[
            'reaction_time']) for p in open_qs.values_list(
            'properties', flat=True) if p['reaction_time']]
        open_median_time = None
        if open_time_serie:
            open_median_time = sum(open_time_serie) / len(open_time_serie)

        return {
            'count': mail_qs.info_counts(),
            'last_status': mail_qs.last_status_counts(),
            'tracking': {
                'opened': mail_qs.opened().count(),
                'open_median_time': open_median_time,
                'clicked': self.get_clicks_count(click_qs, unique=True),
                'clicked_total': self.get_clicks_count(click_qs, unique=False),
                'viewed_in_browser': browser_views
            },
            'timing': {
                'delivery_total': mail_qs.duration().seconds,
                'delivery_median': mail_qs.median('delivery_duration').seconds
            },
            'optout': optout_qs.count_by_origin(with_total=True)
        }

    def to_mail(self, mail, with_body=True):
        """
        @param mail : the Mail instance we want to build the Message for
        @return a EMailMultiAlternatives ready to send
        """

        m = EmailMultiAlternatives(
            subject=self.subject,
            body='',
            from_email=mail.envelope_from,
            to=[mail.recipient])

        m.extra_headers.update({
            settings.CAMPAIGNS['X_USER_ID_HEADER']: str(
                mail.message.author.pk),
            settings.CAMPAIGNS['X_MESSAGE_ID_HEADER']: mail.identifier,
            'Precedence': 'bulk',
            'X-Report-Abuse': 'Please report abuse to {}'.format(
                mail.abuse_url),
            'List-Unsubscribe': '<mailto:{}>, <{}>'.format(
                mail.unsubscribe_addr, mail.unsubscribe_url),
            'Message-ID': mk_msgid(),
            'From': '{} <{}>'.format(
                mail.message.sender_name, mail.message.sender_email),
        })

        post_headers_generation.process(
            m.extra_headers, mail,
            settings.CAMPAIGNS['HEADERS_FILTERS_PARAMS'])

        if with_body:
            plaintext, html = self.mk_body(mail)
            m.body = plaintext
            m.attach_alternative(html, "text/html")

            # attachments
            for a in self.attachments.all():
                m.attach(*a.to_email_attachment())

        return m

    @save_timer(name='campaigns.Message.mk_body')
    def mk_body(self, mail):
        generation_kwargs = {
            'track_open': self.track_open,
            'track_clicks': self.track_clicks,
            'unsubscribe_url': mail.unsubscribe_url,
            'app_url': self.get_app_url(),
            'links_map': self.msg_links or {},
            'mail_properties': mail.properties,
            'mail_identifier': mail.identifier,
            'no_unsubscribe_placehoder_must_raise': True,
            'web_view_url': mail.web_view_url
        }

        plaintext = post_individual_plaintext_generation.process(
            self.mk_plaintext(), **generation_kwargs)

        html = post_individual_html_generation.process(
            self.mk_html(), **generation_kwargs)

        # Use max line length from RFC2822 (78) instead of RFC5322 (998)
        # to force conversion to quoted-printable in almost all cases
        # The idea is to avoid anarchic line-breaks in 7bits
        # formatted mails which cause bad display of some utf-8 characters
        # on some webmails.
        # Note: this might cause problems in non-western character sets...
        django.core.mail.message.RFC5322_EMAIL_LINE_LENGTH_LIMIT = 78
        # Also remove blank lines and leading/trailing spaces in HTML
        # content to make generated body more concise
        for exp in (r'^\s*$', r'^\s+', r'\s+$'):
            html = re.sub(exp, '', html, flags=re.MULTILINE)

        return plaintext, html

    def mk_plaintext(self):
        try:
            h = html2text.HTML2Text()
            h.ignore_images = True
            h.inline_links = False
            h.wrap_links = False
            h.unicode_snob = True  # Prevents accents removing
            h.skip_internal_links = True
            h.ignore_anchors = True
            h.body_width = 0
            h.use_automatic_links = True
            h.ignore_tables = True
        except html.parser.HTMLParseError as e:
            raise WrongHTML(e)

        return h.handle(self.mk_html())

    def mk_html(self):
        """Simply calls configured html template filters

        See settings.CAMPAIGNS['HTML_TEMPLATE_FILTERS']
        """
        # Doctype gets frequently removed by content filters, so we save
        # it...
        doc = lxml.etree.HTML(self.html)
        doctype = ''
        if doc is not None:
            doctype = doc.getroottree().docinfo.doctype

        # ... we process content...
        mangled_content = post_template_html_generation.process(
            self.html,
            detach_images=self.detach_images,
            organization=self.author.organization)

        # And we re-inject it
        return '{}\n{}'.format(doctype, mangled_content)

    def spam_check(self):
        """ Requires the current message to be saved """
        # create dummy message
        mail = Mail(
            recipient='foo@example.com', message=self,
            creation_date=timezone.now(), identifier='i-am-a-test-uuid')
        message = mail.as_message()
        try:
            sc = SpamChecker(
                port=settings.SPAMD_PORT, host=settings.SPAMD_HOST)
        except AttributeError:
            sc = SpamChecker(settings.SPAMD_SERVICE_NAME)

        try:
            return sc.check(message.message().as_string())
        except SpamCheckerError as e:
            error_message = _(
                "Spam checker not available for now: {}").format(e)
            log.error(error_message)
            return SpamResult(-1, False, [], error=error_message)

    def notify(self, state):
        """
        Send email notifications based on current message state

        @param state : a valid value for Message.status
        """
        if not self.author.organization.settings.notify_message_status \
                or not self.author.organization.contact_email:
            return
        if state == Message.SENDING:
            message = NotificationMessage(
                subject=render_to_string(
                    'campaigns/sending_notice_email_subject.txt', {
                        'product_name': settings.PRODUCT_NAME,
                        'name': self.name}).strip(),
                template='campaigns/sending_notice_email.txt',
                render_context={'message': self},
                to=self.author.organization.contact_email,
            )
            message.add_html_part_if_exists(
                'campaigns/sending_notice_email.html')
            message.send()
        elif state == Message.SENT:
            stats = self.mk_stats()
            message = NotificationMessage(
                subject=render_to_string(
                    'campaigns/sending_done_notice_email_subject.txt', {
                        'product_name': settings.PRODUCT_NAME,
                        'name': self.name}).strip(),
                template='campaigns/sending_done_notice_email.txt',
                render_context={'message': self, 'stats': stats},
                to=self.author.organization.contact_email,
            )
            message.add_html_part_if_exists(
                'campaigns/sending_done_notice_email.html')
            message.send()

    def start_sending(self):
        from .tasks import send_mail

        with transaction.atomic():
            # Then, handle all ignored emails (optouts)
            now = timezone.now()
            for i in self.mails.not_legit_for(self):
                MailStatus.objects.create(
                    mail=i, status=MailStatus.IGNORED,
                    creation_date=timezone.now(),
                    raw_msg='Ignored because of previous optout {}'.format(
                        i.get_related_optout()))

            # Then, handle the legit ones
            if not self.send_date:
                self.send_date = timezone.now()
                self.save()
            self.notify(Message.SENDING)
            # locking ?
            legit_mails = self.mails.legit_for(self)
            now = timezone.now()
            MailStatus.objects.bulk_create([
                MailStatus(
                    mail=i, status=MailStatus.QUEUED,
                    creation_date=now, raw_msg='Enqueued in celery')
                for i in legit_mails])
            # bulk_create do not update Mail (too high db cost)
            legit_mails.update(
                curstatus=MailStatus.QUEUED, latest_status_date=now)
            # end_locking ?
            tasks = celery.group([send_mail.s(m.pk) for m in legit_mails])
            log.info('Starting sending {} (#{}) to {} recipients.'.format(
                self, self.pk, len(tasks)))

        tasks.apply_async()

    def has_no_msg_issues(self):
        return not self.has_msg_issues()

    def has_msg_issues(self):
        return self.msg_issue != ''

    def field_changed_and_exists(self, field):
        new_val = getattr(self, field)

        if new_val:
            try:
                old_instance = Message.objects.get(pk=self.pk)
                old_val = getattr(old_instance, field)
                return new_val != old_val
            except Message.DoesNotExist:
                return bool(new_val)

    @save_timer(name='campaigns.Message.build_message')
    def build_message(self):
        if self.html:
            if (self.field_changed_and_exists('html') or
                    self.field_changed_and_exists('subject')):
                if self.status != self.SENT:
                    self.msg_issue = ''
                    try:
                        self.mk_html()
                        self.mk_plaintext()
                    except Exception as e:
                        self.msg_issue = str(e)
                    else:
                        if self.is_spam:
                            self.msg_issue = (
                                _('Message detected as spam'))

                    if self.msg_issue:
                        self.status = self.MSG_ISSUES
                    else:
                        if self.status not in ('sending', 'sent'):
                            self.status = self.MSG_OK
        else:
            self.msg_issue = _('No HTML body given')
            self.status = self.MSG_ISSUES

    @save_timer(name='campaigns.Message.update_spam_score')
    def update_spam_score(self):
        if not settings.CAMPAIGNS['SKIP_SPAM_CHECK'] and (
                self.field_changed_and_exists('html') or
                ((len(self.html) > 0) and
                    self.field_changed_and_exists('subject'))) and (
                        self.status != self.SENDING):

            result = self.spam_check()
            self.spam_score = result.score
            self.spam_details = result.checks
            self.is_spam = result.is_spam
            self.spam_check_error = result.error

    @save_timer(name='campaigns.Message.extract_message_links')
    def extract_message_links(self):
        if self.field_changed_and_exists('html') and self.track_clicks:
            self.msg_links = get_msg_links(self.html)

    @save_timer(name='campaigns.Message.validate_html')
    def validate_html(self):
        errors = []
        if not self.html or self.html.isspace():
            errors.append(_("HTML field can not be empty"))
        elif self.field_changed_and_exists('html'):
            try:
                mail = Mail(
                    recipient='foo@example.com', message=self,
                    creation_date=timezone.now(),
                    identifier='i-am-a-test-uuid')
                self.mk_body(mail)
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise ValidationError({'html': errors})

    def clean_fields(self, exclude):
        if html not in exclude:
            self.validate_html()
        super().clean_fields(exclude)

    def clean(self):
        super().clean()
        if self.external_optout and not \
                self.author.organization.can_external_optout:
            raise ValidationError(
                _("External optout forbidden. Please contact us."))

    def save(self, *args, **kwargs):
        self.validate_html()
        self.extract_message_links()
        self.update_spam_score()
        self.build_message()

        # Keep previous object state
        previous_message = None
        if self.pk:
            previous_message = Message.objects.get(pk=self.pk)

        super().save(*args, **kwargs)

        # Check if transition is message_ok to sending
        if previous_message and \
                previous_message.status == Message.MSG_OK and \
                self.status == Message.SENDING:
            self.start_sending()

    ###############
    # Transitions #
    ###############
    @transition(field=status, source=NEW, target=MSG_ISSUES)
    def new_message_issues(self):
        pass

    @transition(field=status, source=NEW, target=MSG_OK)
    def new_message_ok(self):
        pass

    @transition(field=status, source=MSG_OK, target=MSG_ISSUES)
    def updated_message_issues(self):
        pass

    @transition(field=status, source=MSG_ISSUES, target=MSG_OK)
    def updated_message_ok(self):
        pass

    @transition(field=status, source=MSG_OK, target=SENDING)
    def prepare_sending(self):
        if not settings.BYPASS_DNS_CHECKS:
            domain = self.get_sending_domain()
            if not domain or not domain.is_valid():
                raise ValidationError(_(
                    'Your sending domain is not configured correctly. '
                    'Message can not be sent.'))

    @transition(field=status, source=SENDING, target=SENT)
    def complete_sending(self):
        self.completion_date = timezone.now()
        log.info('Finished sending {} (#{}).'.format(self, self.pk))

        self.notify(Message.SENT)


def get_attachment_storage_path(obj, filename):
    return join('attachments', str(obj.message.pk), filename)


class MessageAttachment(AbstractOwnedModel):
    file = models.FileField(
        upload_to=get_attachment_storage_path,
        verbose_name=_('attached file'))
    original_name = models.CharField(
        max_length=100, verbose_name=_('original name'))
    b64size = models.PositiveIntegerField(
        default=0, verbose_name=_('base 64 size'))
    message = models.ForeignKey(
        Message, related_name='attachments', verbose_name=_('message'))

    owner_path = 'message__author__organization'
    author_path = 'message__author'

    class Meta(AbstractOwnedModel.Meta):
        pass

    def save(self, *args, **kwargs):
        self.b64size = len(b64encode(self.file.read()))
        if not self.original_name:
            self.original_name = self.file.name[:100]
        # Go back to the beggining of the file for later
        self.file.seek(0)
        super().save(*args, **kwargs)

    @property
    def size(self):
        # Handle case where blob has been deleted
        try:
            return self.file.size
        except:
            return None

    @property
    def size_in_mail(self):
        return self.b64size

    @property
    def mimetype(self):
        """ Readable mimetype, guessed from file content """
        self.file.open()
        return magic.from_buffer(self.file.read(1024), mime=True)

    @property
    def path(self):
        # Handle case where blob has been deleted
        try:
            return self.file.path
        except:
            return None

    def to_email_attachment(self):
        mime_type = self.mimetype
        self.file.open()
        if mime_type.startswith('text/'):
            charset = chardet.detect(self.file.read(1024))
            self.file.open()
            if charset.get('encoding'):
                content = self.file.read().decode(charset['encoding'])
            else:
                content = self.file.read().decode('utf-8', 'surrogatescape')
        else:
            content = self.file.read()
        return (self.filename(), content, mime_type)

    def filename(self):
        return self.original_name

    def __str__(self):
        return self.filename()


class PreviewMail(BaseMail):
    """
    Like a Mail, but created by a preview_send API call

    We keep them appart not to mess up stats and so. PreviewMail are not even
    exposed through API.
    """
    def as_message(self, *args, **kwargs):
        message = super().as_message(*args, **kwargs)
        message.subject = '[TEST] ' + message.subject
        return message

    def save(self, *args, **kwargs):
        if not self.id:
            # put a clear preview identifier
            self.identifier = 'preview' + mk_base64_uuid()
        super().save(*args, **kwargs)

    @classmethod
    def send_preview(cls, mail_id):
        mail = cls.objects.get(pk=mail_id)
        message = mail.as_message()

        backend = Backend()
        backend.send_simple_message(message)
        log.debug('[{}] Sent preview to {} for message {}'.format(
            mail.identifier, mail.recipient, mail.message.identifier))
        return 'Sent preview {}'.format(mail.identifier)
