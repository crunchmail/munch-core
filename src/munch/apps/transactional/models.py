import urllib
from email.utils import parseaddr
from email.header import make_header
from email.header import decode_header

from django.db import models
from django.urls import reverse
from django.conf import settings
from django.contrib.postgres.fields import HStoreField
from django.utils.translation import ugettext_lazy as _
from slimta.envelope import Envelope

from munch.core.mail.utils import mk_base64_uuid
from munch.core.mail.models import RawMail
from munch.core.mail.models import AbstractMail
from munch.core.mail.models import BaseMailQuerySet
from munch.core.mail.models import AbstractMailStatus
from munch.core.utils.models import AbstractOwnedModel
from munch.core.utils.managers import OwnedModelQuerySet

from munch.apps.users.models import MunchUser
from munch.apps.campaigns.models import Category
from munch.apps.domains.models import SendingDomain

from .munchers import headers_filters


class MailBatch(AbstractOwnedModel):
    creation_date = models.DateTimeField(
        verbose_name=_('creation date'), auto_now_add=True)
    identifier = models.CharField(
        max_length=35, db_index=True, unique=True, editable=False,
        default=mk_base64_uuid, verbose_name=_('identifier'))
    name = models.CharField(_('name'), max_length=60)
    author = models.ForeignKey(MunchUser, verbose_name=_('author'))
    category = models.ForeignKey(
        Category, null=True, blank=True,
        related_name='mailbatches', verbose_name=_('category'))
    msg_links = HStoreField(
        verbose_name=_('message links'), null=True, blank=True)

    owner_path = 'author__organization'
    author_path = 'author'

    class Meta:
        verbose_name = _('mail batch')
        verbose_name_plural = _('mail batches')
        unique_together = [('author', 'name')]

    def __str__(self):
        return '{}'.format(self.identifier)

    def get_organization(self):
        return self.author.organization

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

    def mk_stats(self):
        from munch.apps.tracking.models import TrackRecord
        from munch.apps.tracking.models import READ_BROWSER
        from munch.apps.optouts.models import OptOut

        mail_qs = self.mails.all()

        open_identifiers = self.mails.filter(
            track_open=True).values_list('identifier', flat=True)
        clicks_identifiers = self.mails.filter(
            track_clicks=True).values_list('identifier', flat=True)

        click_qs = TrackRecord.objects.filter(
            identifier__in=clicks_identifiers, kind='click')
        open_qs = TrackRecord.objects.filter(
            identifier__in=open_identifiers, kind='read').order_by(
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


def get_mail_identifier():
    return mk_base64_uuid('t-')


class MailQuerySet(BaseMailQuerySet, OwnedModelQuerySet):
    pass


class Mail(AbstractOwnedModel, AbstractMail):
    identifier = models.CharField(
        max_length=35, db_index=True, unique=True,
        default=get_mail_identifier, verbose_name=_('identifier'))
    headers = HStoreField(verbose_name=_('headers'))
    message = models.ForeignKey(
        RawMail, on_delete=models.SET_NULL, verbose_name=_('message'),
        null=True, related_name='transactional_mail')
    sender = models.EmailField(verbose_name=_('sender'))
    author = models.ForeignKey(MunchUser, verbose_name=_('author'))
    batch = models.ForeignKey(
        MailBatch, null=True, blank=True,
        verbose_name=_('batch'), related_name='mails')
    track_open = models.BooleanField(
        _('track opens'), default=False,
        help_text=(_("Detect who opens message by adding hidden image.")))
    track_clicks = models.BooleanField(
        _('track clicks'), default=False,
        help_text=_(
            "Detect which links were clicked by replacing "
            "original links by redirections"))
    msg_links = HStoreField(
        verbose_name=_('message links'), null=True, blank=True)
    curstatus = models.CharField(
        max_length=20,
        default=AbstractMailStatus.UNKNOWN,
        choices=AbstractMailStatus._meta.get_field('status').choices,
        verbose_name=_('current status'))

    objects = BaseMailQuerySet.as_manager()

    owner_path = 'author__organization'
    author_path = 'author'

    @classmethod
    def unsubscribe_url(cls, identifier, author, sending_domain):
        from munch.core.mail.utils import get_app_url

        relative_url = reverse(
            'unsubscribe', kwargs={'identifier': identifier})
        organization_app_url = get_app_url(
            organization=author.organization, domain=sending_domain)
        return urllib.parse.urljoin(organization_app_url, relative_url)

    def get_sending_domain(self):
        all_domains = SendingDomain.objects
        org_id = self.get_organization()
        qs = all_domains.filter(organization=org_id) | all_domains.filter(
            alt_organizations__in=[org_id])
        organization_domains = qs.distinct()
        return organization_domains.get_from_email_addr(
            parseaddr(self.headers.get('From'))[1], must_raise=False)

    def get_app_url(self):
        from munch.core.mail.utils import get_app_url

        return get_app_url(
            domain=self.get_sending_domain(),
            organization=self.get_organization())

    def get_organization(self):
        return self.author.organization

    def get_category(self):
        if self.batch and self.batch.category:
            return self.batch.category

    @classmethod
    def get_envelope(cls, identifier):
        from .utils import get_envelope_from_identifier
        return get_envelope_from_identifier(identifier)

    def as_envelope(self, must_raise=True):
        envelope = Envelope()

        headers_filters.process(
            self.headers, self,
            settings.TRANSACTIONAL['HEADERS_FILTERS_PARAMS'])

        headers = ""
        for key, value in self.headers.items():
            if key in ('Subject', ):
                header = make_header(
                    decode_header(value), header_name=key, maxlinelen=78)
                value = header.encode(linesep='\r\n')
            headers += "{}: {}\n".format(key, value)

        message = ""
        if self.message:
            message = self.message.content or ""

        if self.message is None and must_raise:
            raise Exception(
                "Can't build this envelope because "
                "there is no RawMail attached to it.")
        envelope.parse(headers.encode('utf-8') + message.encode('utf-8'))
        envelope.sender = self.sender
        envelope.recipients.append(self.recipient)
        return envelope

    def get_original_links(self, links):
        original_links = {}
        for link in links:
            original_links[link] = self.msg_links.get(link)
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


class MailStatus(AbstractOwnedModel, AbstractMailStatus):
    mail = models.ForeignKey(
        Mail, related_name='statuses', verbose_name=_('mail'))

    owner_path = 'mail__author__organization'
    author_path = 'mail__author'

    class Meta:
        verbose_name = _('mail status')
        verbose_name_plural = _('mail statuses')
        get_latest_by = 'creation_date'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        must_save_mail = False
        if self.status in self.FINAL_STATES:
            self.mail.message = None
            must_save_mail = True
        if self.status == AbstractMailStatus.DROPPED:
            self.mail.had_delay = True
            must_save_mail = True
        if must_save_mail:
            self.mail.save()

    def __str__(self):
        return _('Message {} is {}').format(self.mail.identifier, self.status)
