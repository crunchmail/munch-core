from django.db import models
from django.db.models import Count
from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.template.loader import render_to_string

from munch.core.utils.models import AbstractOwnedModel
from munch.core.utils.managers import OwnedModelQuerySet
from munch.core.mail.utils.emails import NotificationMessage
from munch.apps.users.models import MunchUser


class OptOutManager(models.Manager):
    def create_or_update(
            self, identifier, address, origin,
            author=None, category=None, creation_date=None):
        """
        OptOuts from a Mail

        No matter if it already have a previous optout or not : create one or
        update the existing.
        """
        from .models import OptOut

        creation_date = creation_date or timezone.now()
        obj, created = OptOut.objects.get_or_create(
            identifier=identifier, address=address,
            defaults={
                'author': author, 'category': category,
                'origin': origin, 'creation_date': creation_date})
        if not created:
            obj.origin = OptOut.BY_WEB
            obj.creation_date = timezone.now()
            obj.save()


class OptOutQueryset(OwnedModelQuerySet):
    def count_by_origin(self, with_total=False):
        """
        Returns a dict with count for each optout origin

        It lists even optout origins with zero occurence for that queryset
        """
        from .models import OptOut

        d = {i: 0 for i, _ in OptOut._meta.get_field('origin').choices}
        d.update(self.values_list('origin').annotate(count=Count('origin')))
        if with_total:
            d['total'] = sum(d.values())
        return d

    def for_email(self, address):
        return self.filter(address=address).first()


class OptOut(AbstractOwnedModel):
    BY_MAIL = 'mail'
    BY_WEB = 'web'
    BY_FBL = 'feedback-loop'
    BY_BOUNCE = 'bounce'
    BY_ABUSE = 'abuse'
    BY_API = 'api'

    identifier = models.CharField(
        max_length=150, db_index=True,
        unique=True, verbose_name=_('identifier'))
    address = models.EmailField(verbose_name=_('mail'))
    creation_date = models.DateTimeField(default=timezone.now)
    origin = models.CharField(
        _('origine'), max_length=20, choices=(
            (BY_MAIL, _('Email')),
            (BY_WEB, _('Web link')),
            (BY_FBL, _('Detected as spam')),
            (BY_ABUSE, _("By abuse report")),
            (BY_BOUNCE, _('Too much delivering errors'))))
    author = models.ForeignKey(
        MunchUser, verbose_name=_('author'), null=True, blank=True)
    category = models.ForeignKey(
        'core.Category', verbose_name=_('category'), null=True, blank=True)

    objects = OptOutManager.from_queryset(OptOutQueryset)()

    class Meta(AbstractOwnedModel.Meta):
        verbose_name = _('optout')
        verbose_name_plural = _('optouts')

    owner_path = 'author__organization'
    author_path = 'author'

    def __str__(self):
        return self.identifier

    def get_organization(self):
        if self.author:
            return self.author.organization

    def notify_new_optout(self):
        from munch.core.utils import get_mail_by_identifier

        if not self.author:
            return

        organization = self.author.organization

        if organization.settings.notify_optouts and \
                organization.contact_email:
            mail = get_mail_by_identifier(self.identifier)
            message = mail.message
            origin = self.get_origin_display()

            message = NotificationMessage(
                subject=render_to_string(
                    'optouts/optout_notification_email_subject.txt', {
                        'product_name': settings.PRODUCT_NAME,
                        'address': self.address,
                        'origin': self.origin}).strip(),
                template='optouts/optout_notification_email.txt',
                render_context={
                    'to': self.address,
                    'origin': origin,
                    'message': message},
                to=organization.contact_email,
            )
            message.add_html_part_if_exists(
                'optouts/optout_notification_email.html')
            message.send()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.notify_new_optout()
