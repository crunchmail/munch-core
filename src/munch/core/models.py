from django.db import models
from django.utils.translation import ugettext_lazy as _

from munch.core.utils.models import AbstractOwnedModel

from .signals import pre_validation
from .signals import post_validation


class Category(AbstractOwnedModel):
    name = models.CharField(_('name'), max_length=100)
    author = models.ForeignKey('users.MunchUser', verbose_name=_('author'))

    owner_path = 'author__organization'
    author_path = 'author'

    class Meta(AbstractOwnedModel.Meta):
        verbose_name = _('category')
        verbose_name_plural = _('categories')

    def __str__(self):
        return self.name

    def mk_stats(self):
        from munch.apps.optouts.models import OptOut
        from munch.apps.campaigns.models import Mail as CampaignMail

        campaign_mail_qs = CampaignMail.objects.filter(message__category=self)
        optout_qs = OptOut.objects.filter(
            identifier__in=campaign_mail_qs.values_list(
                'identifier', flat=True))

        return {
            'count': campaign_mail_qs.info_counts(),
            'last_status': campaign_mail_qs.last_status_counts(),
            'timing': {
                'delivery_median': campaign_mail_qs.median(
                    'delivery_duration').seconds
            },
            'optout': optout_qs.count_by_origin(with_total=True)
        }


class ValidationSignalsModel:
    def clean(self, *args, **kwargs):
        created = True
        if self.pk:
            created = False

        pre_validation.send(
            sender=self.__class__, instance=self, created=created)
        super().clean(*args, **kwargs)
        post_validation.send(
            sender=self.__class__, instance=self, created=created)
