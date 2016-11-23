import hashlib
import datetime
from collections import Counter
from collections import defaultdict

import msgpack
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.contrib.postgres.fields import HStoreField
from django_redis import get_redis_connection

from munch.core.utils import get_mail_by_identifier
from munch.core.mail.models import AbstractMailStatus

conn = get_redis_connection('default')

READ_MUA_PIXEL = 'pixel'
READ_CLICK = 'click'
READ_BROWSER = 'browser'
READ_SOURCES = {
    READ_MUA_PIXEL: 'MUA tracking pixel',
    READ_BROWSER: 'View-in-browser link',
    READ_CLICK: 'Click on a tracked link'}


class TrackRecordQuerySet(models.QuerySet):
    def bulk_create(self, objs, *args, **kwargs):
        for track_record in objs:
            track_record.update_cached_fields()

        created_records = super().bulk_create(objs, *args, **kwargs)
        return created_records

    def count_by_url(self, msg_links, include_any=False, unique=False):
        """
        Returns click count for each URL in the set

        No more than a click per identifier is accounted if unique is True

        :param include_any: adds an extra entry to count mails that have been
                            clicked at least once
        :rtype:             A dict url->int
        """
        click_occurences = self.values(
            'properties', 'identifier').distinct()
        click_lists = defaultdict(list)
        for occ in click_occurences:
            click_lists[occ['identifier']].append(
                msg_links.get(occ['properties']['link']))
        click_lists = dict(click_lists)

        if unique:
            click_lists = {k: list(set(v)) for k, v in click_lists.items()}

        click_counts = Counter()
        for urls in click_lists.values():
            click_counts = click_counts + Counter(urls)
        click_counts = dict(click_counts)

        if include_any:
            click_counts['any'] = len(click_lists.keys())
        return click_counts


class TrackRecord(models.Model):
    identifier = models.CharField(
        max_length=150, db_index=True, verbose_name=_('identifier'))
    kind = models.CharField(
        max_length=50, db_index=True, verbose_name=_('kind'))
    properties = HStoreField(
        null=True, blank=True, verbose_name=_('properties'))
    creation_date = models.DateTimeField(_('creation date'), auto_now_add=True)

    objects = models.Manager.from_queryset(TrackRecordQuerySet)()

    class Meta:
        ordering = ['creation_date']

    def __str__(self):
        return '{} ({})'.format(self.identifier, self.kind)

    @classmethod
    def clear_cache(cls):
        count = 0
        for key in conn.scan_iter('tr:*'):
            count += conn.delete(key)
        return count

    @classmethod
    def get_from_cache(self, identifier, kind=None):
        key = 'tr:{}'.format(identifier)
        records = []
        if kind:
            key += ':{}'.format(kind)
        keys = conn.keys('{}*'.format(key))
        if keys:
            for record in conn.mget(keys):
                record = msgpack.unpackb(record, encoding='utf-8')
                record['creation_date'] = datetime.datetime.fromtimestamp(
                    int(record['creation_date']))
                record.update({'identifier': identifier})
                records.append(record)
            records = sorted(records, key=lambda k: k['creation_date'])
        return records

    def save(self, update_cache=False, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = timezone.now()

        if not self.pk or update_cache:
            self.update_cached_fields()

        if self.kind == 'click' and not TrackRecord.objects.filter(
                identifier=self.identifier, kind='read').exists():
            TrackRecord.objects.create(
                identifier=self.identifier,
                creation_date=self.creation_date,
                kind='read', properties={'source': READ_CLICK})

        super().save(*args, **kwargs)

        self.cache()

    def cache(self):
        return conn.set(
            'tr:{}:{}:{}'.format(self.identifier, self.kind, self.pk),
            msgpack.packb({
                'properties': self.properties,
                'creation_date': self.creation_date.timestamp()}))

    def update_cached_fields(self):
        mail = get_mail_by_identifier(self.identifier)
        delivered_status = mail.statuses.filter(
            status=AbstractMailStatus.DELIVERED).first()
        if delivered_status:
            t = self.creation_date - delivered_status.creation_date
        else:
            t = datetime.timedelta()
        self.properties['reaction_time'] = str(int(t.total_seconds()))


class LinkMapManager(models.Manager):
    def get_identifier(self, link):
        hasher = hashlib.md5()
        if isinstance(link, bytes):
            hasher.update(link)
        else:
            hasher.update(link.encode('utf-8'))
        return hasher.hexdigest()

    def get_or_create(self, defaults=None, **kwargs):
        identifier = self.get_identifier(kwargs.get('link'))
        try:
            return self.get(identifier=identifier), False
        except self.model.DoesNotExist:
            return self.create(
                identifier=identifier, link=kwargs.get('link')), True

    def bulk_create(self, objs, *args, **kwargs):
        # Generate identifiers and deduplicate
        identifiers = []
        to_create = []
        for obj in objs:
            identifier = self.get_identifier(obj.link)
            if identifier not in identifiers:
                identifiers.append(identifier)
                obj.identifier = identifier
                to_create.append(obj)

        existings = self.filter(identifier__in=identifiers)
        existings_identifiers = [obj.identifier for obj in existings]
        objs = []
        for obj in to_create:
            if obj.identifier not in existings_identifiers:
                objs.append(obj)
        return super().bulk_create(objs, *args, **kwargs) + list(existings)


class LinkMap(models.Model):
    identifier = models.CharField(
        max_length=50, db_index=True,
        unique=True, verbose_name=_('identifier'))
    link = models.URLField(verbose_name=_('link'), max_length=500)

    objects = LinkMapManager()

    def __str__(self):
        return '"{}" as "{}"'.format(self.link, self.identifier)

    def save(self, *args, **kwargs):
        if not self.identifier:
            self.identifier = LinkMap.objects.get_identifier(self.link)
        super().save(*args, **kwargs)
