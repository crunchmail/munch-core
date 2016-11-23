from django.db import models
from django.core.validators import validate_email
from django.utils.translation import ugettext_lazy as _

from munch.apps.campaigns.models import Mail


class AbuseNotification(models.Model):
    mail = models.ForeignKey(Mail, verbose_name=_('mail'))
    date = models.DateTimeField(auto_now=True, verbose_name=_('date'))
    contact_name = models.CharField(
        _('contact name'), max_length=100, blank=True)
    contact_email = models.CharField(
        _('contact email'), validators=[validate_email],
        max_length=50, blank=True)
    comments = models.TextField(_('comments'))

    class Meta:
        verbose_name = _("abuse report")
        verbose_name_plural = _("abuse reports")

    def __str__(self):
        return _('Abuse report by {}').format(self.mail.recipient)
