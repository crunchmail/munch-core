import logging
import datetime

from django.db import models
from django.db.models import F
from django.db.models import Max
from django.db.models import Min
from django.db.models import Manager
from django.db.models import ExpressionWrapper

from munch.core.mail.models import BaseMailQuerySet
from munch.core.mail.models import BaseMailStatusQuerySet
from munch.core.utils.managers import OwnedModelQuerySet

log = logging.getLogger('munch')


class MailStatusQuerySet(OwnedModelQuerySet, BaseMailStatusQuerySet):
    pass


class MailManager(Manager):
    def create(self, *args, **kwargs):
        from .models import MailStatus

        mail = super().create(*args, **kwargs)
        MailStatus.objects.create(
            mail=mail, status=MailStatus.UNKNOWN,
            creation_date=mail.creation_date,
            raw_msg='Mail passed to infrastructure')
        return mail

    def bulk_create(self, objs, update_status=True, *args, **kwargs):
        from .models import Mail
        from .models import MailStatus

        # same enhancement as create, but on already instanciated objs
        for i in objs:
            i.identifier = Mail._meta.get_field('identifier').default()

        created_mails = super().bulk_create(objs, *args, **kwargs)

        # Get all Mails without an initial_status. May be improved if
        # https://code.djangoproject.com/ticket/19527 gets merged.

        # FYI: on a 1000 mails insert, the bulk_create of statuses takes ~0.8s
        # out of 4.8s
        if update_status:
            statuses = [MailStatus(
                mail=i, creation_date=i.creation_date,
                status=MailStatus.UNKNOWN,
                raw_msg='Mail passed to infrastructure')
                for i in self.filter(statuses=None)]

            MailStatus.objects.bulk_create(statuses)

        # Manually update mails cached attributs base on
        # `date`, `message` and cached fields as None.
        # Why manually and not with signal ?
        #   => https://git.owk.cc/crunchmail/munch/issues/2012#note_2757
        #
        # /!\ Warning /!\ This part will only work with bulk_create
        # for emails that have same `Message` instance.
        message, created_date = None, None
        if created_mails:
            message = getattr(created_mails[0], 'message')
            created_date = getattr(created_mails[0], 'creation_date')
        if message and created_date:
            self.model.objects.filter(
                creation_date=created_date, message=message,
                first_status_date=None, latest_status_date=None).update(
                    had_delay=False,
                    first_status_date=F('creation_date'),
                    latest_status_date=F('creation_date'),
                    curstatus=MailStatus.UNKNOWN,
                    delivery_duration=datetime.timedelta())

        return created_mails


class MailQuerySet(OwnedModelQuerySet, BaseMailQuerySet):
    def _legit_exclusionlist(
            self, message, include_bounces=False, include_optouts=False):
        from .models import OptOut

        exclusion_list = []

        if not include_bounces:
            exclusion_list += OptOut.objects.filter(
                origin=OptOut.BY_BOUNCE).values_list('address', flat=True)

        if not include_optouts:
            # If we define a category, the optouts are valid in this category
            # and thats all.
            if message.category:
                exclusion_list += OptOut.objects.exclude(
                    origin=OptOut.BY_BOUNCE).filter(
                        category=message.category).values_list(
                            'address', flat=True)
            else:
                organization = message.author.organization
                exclusion_list += OptOut.objects.exclude(
                    origin=OptOut.BY_BOUNCE).filter(
                        author__organization=organization).values_list(
                            'address', flat=True)

        return exclusion_list

    def legit_for(self, *args, **kwargs):
        return self.exclude(
            recipient__in=self._legit_exclusionlist(*args, **kwargs))

    def not_legit_for(self, *args, **kwargs):
        return self.filter(
            recipient__in=self._legit_exclusionlist(*args, **kwargs))

    def with_bounds(self):
        return self.annotate(
            start=Min('statuses__creation_date'),
            end=Max('statuses__creation_date')).annotate(
                statuses_delta=ExpressionWrapper(
                    F('end') - F('start'),
                    output_field=models.DurationField()
                ))
