import sys
import socket
import logging
import hashlib
from datetime import timedelta

from django.db import models
from django.db.models import Count
from django.db.models import Prefetch
from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from ..utils.managers import MedianQuerySetMixin
from .utils import UniqueEmailAddressParser
from .validators import rfc3463_regex
from .validators import rfc3463_regex_validator

log = logging.getLogger('munch')

return_path_parser = UniqueEmailAddressParser(
    domain=lambda: settings.RETURNPATH_DOMAIN, prefix='return-')

unsubscribe_parser = UniqueEmailAddressParser(
    domain=lambda: settings.RETURNPATH_DOMAIN, prefix='unsubscribe-')


class TrackingSummary:
    def _get_first_open(self):
        from munch.apps.tracking.models import TrackRecord

        if self._first_open_record is None:
            self._first_open_record = False
            record = TrackRecord.get_from_cache(
                self.mail.identifier, kind='read')
            if record:
                self._first_open_record = record[0]
        return self._first_open_record

    def first_open(self):
        record = self._get_first_open()
        if record:
            return record['creation_date']
        return None

    def open_time(self):
        record = self._get_first_open()
        if record:
            return int(record['properties'].get('reaction_time', 0))
        return 0

    def clicks(self):
        from munch.apps.tracking.models import TrackRecord

        results = []
        records = TrackRecord.get_from_cache(
            self.mail.identifier, kind='click')
        identifiers = [l['properties'].get('link') for l in records]
        links = self.mail.get_original_links(identifiers)
        for record in records:
            results.append(
                {links[record['properties'].get(
                    'link')]: record['creation_date']})
        return results

    def __init__(self, mail):
        self.mail = mail
        self._first_open_record = None


class BaseMailStatusManager(models.Manager):
    def re_run_signals(self, since, mail_path='mail'):
        from munch.core.mail import backend

        limit = 1000
        queryset = self.filter(
            creation_date__gte=timezone.now() - timedelta(seconds=since)).only(
                'pk', 'source_ip', 'destination_domain',
                'status', 'creation_date', mail_path).prefetch_related(
                    Prefetch(
                        mail_path,
                        self.model.mail.field.remote_field
                        .model.objects.all().only('identifier')))
        count = queryset.count()
        rest = count % limit
        for page in range(0, int(count / limit)):
            start = page * limit
            end = start + limit
            sys.stdout.flush()
            sys.stdout.write('Re running from {} to {} (total:{})...\r'.format(
                start, end, count))
            for mailstatus in queryset[start:end]:
                mailstatus.pk = None
                backend.pre_save_mailstatus_signal(
                    sender=self, instance=mailstatus, raw=False)
                backend.post_save_mailstatus_signal(
                    sender=self, instance=mailstatus, created=True, raw=False)

        if rest:
            sys.stdout.write(
                'Re running the latest statuses (total:{})...\r'.format(rest))
        for mailstatus in queryset.all()[count - rest:count]:
            mailstatus.pk = None
            backend.pre_save_mailstatus_signal(
                sender=self, instance=mailstatus, raw=False)
            backend.post_save_mailstatus_signal(
                sender=self, instance=mailstatus, created=True, raw=False)

        return count


class BaseMailStatusQuerySet(models.QuerySet):
    def bounces(self):
        return self.filter(status__in=(
            AbstractMailStatus.BOUNCED, AbstractMailStatus.DROPPED))

    def duration(self):
        """ Duration on which spans a qs of MailStatus

        :returns: a datetime.timedelta
        """
        extrems = self.aggregate(
            end=models.Max('creation_date'), start=models.Min('creation_date'))

        if not extrems['end'] or not extrems['start']:
            # case of empty qs (None values) -> zero-timedelta
            return timedelta()
        else:
            return extrems['end'] - extrems['start']

    def refresh_mail_cache(self):
        """
        Refresh Mail attributes depending on mailstatuses

        Some attributes on Mail model are bare cache of linked Mailstatuses,
        that function goes through all the mailstatus and syncs their values to
        coresponding Mail instances.
        """
        for status in self.order_by('creation_date'):
            AbstractMailStatus.update_mail_status(
                AbstractMailStatus, status, raw=True)


class AbstractMailStatus(models.Model):
    DELIVERED = 'delivered'
    BOUNCED = 'bounced'
    DELAYED = 'delayed'
    DROPPED = 'dropped'
    DELETED = 'deleted'
    UNKNOWN = 'unknown'
    IGNORED = 'ignored'
    QUEUED = 'queued'
    SENDING = 'sending'

    STATUS_CHOICES = (
        (UNKNOWN, _("unknown")),
        (IGNORED, _("ignored")),
        (DELETED, _("deleted")),
        (QUEUED, _("queued")),
        (SENDING, _("sending")),
        (DELAYED, _("delayed (retrying)")),
        (DELIVERED, _("delivered to remote MTA")),
        (DROPPED, _("not delivered (soft-bounce)")),
        (BOUNCED, _("not delivered (hard-bounce)")),
    )

    FINAL_STATES = (BOUNCED, DELIVERED, IGNORED, DROPPED)
    STATES = tuple([UNKNOWN, SENDING] + list(FINAL_STATES) + [QUEUED])

    status = models.CharField(
        max_length=15, default=QUEUED,
        choices=STATUS_CHOICES, verbose_name=_('status'))
    creation_date = models.DateTimeField(verbose_name=_('creation_date'))
    source_ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name=_('source ip'))
    source_hostname = models.CharField(
        max_length=100, null=True,
        blank=True, verbose_name=_('source hostname'))
    destination_domain = models.CharField(
        max_length=150, verbose_name=_('destination domain'))
    status_code = models.CharField(
        max_length=25, blank=True,
        validators=[rfc3463_regex_validator],
        verbose_name=_('SMTP status code'),
        help_text='X.XXX.XXX, as defined in RFC3463')
    raw_msg = models.TextField(verbose_name=_('raw message'))

    objects = BaseMailStatusManager()

    class Meta:
        abstract = True
        get_latest_by = 'creation_date'
        verbose_name_plural = "Mail Statuses"

    def update_mail_status(self):
        try:
            self.mail.curstatus = self.status
            if not self.pk and not self.creation_date:
                self.creation_date = timezone.now()

            if not self.mail.first_status_date:
                self.mail.first_status_date = self.creation_date
            self.mail.latest_status_date = self.creation_date
            self.mail.delivery_duration = self.mail.latest_status_date \
                - self.mail.first_status_date
            # a mail had issues if it had been softbounced at a certain time.
            self.mail.had_delay = self.mail.had_delay or (
                self.status == AbstractMailStatus.DROPPED)
            # warning : save_base_is not part of the public Django API
            models.Model.save_base(self.mail)
        except self.mail.DoesNotExist:
            pass

    def should_optout(self, create=False):
        from munch.apps.optouts.models import OptOut
        from munch.apps.campaigns.models import (
            MailStatus as CampaignsMailStatus)
        from munch.apps.transactional.models import (
            MailStatus as TransactionalMailStatus)

        filter_kwargs = {
            'mail__recipient': self.mail.recipient,
            'status__in': [self.DROPPED, self.BOUNCED]}

        if OptOut.objects.filter(
                address=self.mail.recipient, origin=OptOut.BY_BOUNCE).exists():
            return True

        bounces = list(CampaignsMailStatus.objects.filter(
            **filter_kwargs).only('creation_date'))
        bounces += list(TransactionalMailStatus.objects.filter(
            **filter_kwargs).only('creation_date'))
        relevant_rule = None
        # Categorize and count the bounces in policies
        for rule in settings.CAMPAIGNS['BOUNCE_POLICY']:
            if self.match_policy(rule):
                relevant_rule = rule
                break

        if relevant_rule is None:
            raise ValueError((
                '"{}" do no match any BOUNCE_POLICY '
                'entry, fix settings.').format(self.status_code))

        # For this rule, count the total number of matching bounces
        count = len([b for b in bounces if b.match_policy(relevant_rule)])

        max_bounces = relevant_rule[1]

        if count >= max_bounces:
            if create:
                log.info(
                    'Unsubscribing {} via bounce'.format(self.mail.recipient))
                OptOut.objects.create_or_update(
                    identifier=self.mail.identifier,
                    address=self.mail.recipient,
                    origin=OptOut.BY_BOUNCE)
            return True
        return False

    def match_policy(self, policy):
        """ does it match the bounce handling policy ?

        @param policy a bounce policy: a 3-uplet:
               - a list of matchs (matches beggining of bounce code)
               - how many bounces before optout (int)
               - how many days back are the bounces counted (int)
        @return a boolean
        """
        matches, how_many, days = policy
        for lookup in matches:
            if (self.status_code.startswith(lookup) and
                    (self.creation_date > (
                        timezone.now() - timedelta(days=days)))):
                return True

        return False

    def save(self, *args, **kwargs):
        created = not self.pk

        self.update_mail_status()

        if self.status_code:
            status_code = rfc3463_regex.match(self.status_code)
            if status_code:
                self.status_code = status_code.group(0)

        if not self.pk:
            if not self.creation_date:
                self.creation_date = timezone.now()
            if not self.source_hostname:
                self.source_hostname = socket.getfqdn()
        super().save(*args, **kwargs)

        if created and self.status in [self.DROPPED, self.BOUNCED]:
            self.should_optout(create=True)


class BaseMailQuerySet(MedianQuerySetMixin, models.QuerySet):
    def done(self):
        return self.filter(
            curstatus__in=AbstractMailStatus.FINAL_STATES).distinct()

    def pending(self):
        return self.exclude(
            curstatus__in=AbstractMailStatus.FINAL_STATES).distinct()

    def duplicate_addrs(self):
        """ Returns a list of couples (count, address) for duplicate mail address

        Usefull on a restricted queryset, for example to find duplicate
        recipients.
        """
        return self.values_list(
            'recipient').annotate(Count('recipient')).exclude(
                recipient__count=1)

    def opened(self):
        """ With triggered open tracker """
        from munch.apps.tracking.models import TrackRecord

        identifiers = self.distinct().values_list('identifier', flat=True)
        opened_identifiers = TrackRecord.objects.filter(
            identifier__in=identifiers, kind='read').values_list(
                'identifier', flat=True)
        return self.filter(identifier__in=opened_identifiers).distinct()

    def clicked(self):
        """ With at least one triggered click tracker """
        from munch.apps.tracking.models import TrackRecord

        identifiers = self.distinct().values_list('identifier', flat=True)
        clicked_identifiers = TrackRecord.objects.filter(
            identifier__in=identifiers, kind='click').values_list(
                'identifier', flat=True)
        return self.filter(identifier__in=clicked_identifiers).distinct()

    def duration(self):
        """ Duration on which spans a qs of MailStatus

        :returns: a timedelta
        """
        extrems = self.aggregate(
            end=models.Max('latest_status_date'),
            start=models.Min('first_status_date'))

        if not extrems['end'] or not extrems['start']:
            # case of empty qs (None values) -> zero-timedelta
            return timedelta()
        return extrems['end'] - extrems['start']

    def last_status_counts(self):
        """ Returns all existing curstatus values in qs """
        statuses = {k: v for k, v in self.values_list(
            'curstatus').annotate(Count('curstatus'))}

        for status in AbstractMailStatus.STATES:
            if status not in statuses:
                statuses[status] = 0
        return statuses

    def info_counts(self):
        """ Counts on certain usefull characteristics of Mails """
        return {
            'done': self.done().count(),
            'had_delay': self.filter(had_delay=True).count(),
            'in_transit': self.pending().count(),
            'total': self.count()}

    def update_cached_fields(self):
        """ Updated cached fields

        Do not have to be called in normal time, and is costly
        (~2h on dev machine for ~1500k Mails)
        """
        # that is not possible without raw SQL :
        # self.with_bounds().update(
        #     first_status_date=F('start'),
        #     latest_status_date=F('end'),
        #     delivery_duration=(F('statuses_delta') - F('start'))
        # )

        qs = self.prefetch_related('statuses').with_bounds()
        log.debug('Starting')
        for i, mail in enumerate(qs):
            mail.first_status_date = mail.start
            mail.latest_status_date = mail.end
            mail.delivery_duration = mail.end - mail.start
            statuses = list(mail.statuses.all())
            # doing the sort on SQL level would ruin prefetch_related benefit
            statuses.sort(key=lambda x: x.creation_date)
            if len(statuses) > 0:
                mail.curstatus = statuses[-1].status
            mail.save()
            if (i % 1000) == 0:
                log.debug(i)


class AbstractMail(models.Model):
    recipient = models.EmailField(verbose_name=_('recipient'))
    creation_date = models.DateTimeField(
        default=timezone.now, verbose_name=_('creation date'))
    first_status_date = models.DateTimeField(
        blank=True, null=True, verbose_name=_('first status date'))
    latest_status_date = models.DateTimeField(
        blank=True, null=True, verbose_name=_('latest status date'))
    delivery_duration = models.DurationField(
        null=True, verbose_name=_('delivery duration'))
    had_delay = models.BooleanField(default=False, verbose_name=_('had delay'))

    objects = BaseMailQuerySet.as_manager()

    class Meta:
        abstract = True
        verbose_name = _('mail')
        verbose_name_plural = _('mails')

    def __str__(self):
        return self.identifier

    @property
    def unsubscribe_addr(self):
        return unsubscribe_parser.new(self.identifier)

    @property
    def envelope_from(self):
        return return_path_parser.new(self.identifier)

    def tracking_info(self):
        return TrackingSummary(self)

    def get_category(self):
        if hasattr(self, 'batch'):
            return self.batch.category
        if hasattr(self, 'message'):
            return self.message.category


class RawMailManager(models.Manager):
    def get_or_create(self, defaults=None, **kwargs):
        content = kwargs.get('content')
        hasher = hashlib.md5()
        if isinstance(content, bytes):
            hasher.update(content)
        else:
            hasher.update(content.encode('utf-8'))
        signature = hasher.hexdigest()
        try:
            return self.get(signature=signature), False
        except self.model.DoesNotExist:
            return self.create(
                signature=signature, content=content), True


class RawMail(models.Model):
    signature = models.CharField(max_length=32, verbose_name=_('signature'))
    content = models.TextField(verbose_name=_('content'))

    objects = RawMailManager()
