import logging

from django.dispatch import receiver
from django.db.models.signals import pre_save
from django.db.models.signals import post_save
from django.db.models.signals import post_delete

from munch.core.mail import backend

from .models import MailStatus
from .models import MessageAttachment

log = logging.getLogger(__name__)

# MailStatus
pre_save.connect(backend.pre_save_mailstatus_signal, sender=MailStatus)
post_save.connect(backend.post_save_mailstatus_signal, sender=MailStatus)


@receiver(post_delete, sender=MessageAttachment)
def auto_delete_message_attachment_on_delete(sender, instance, **kwargs):
    if not instance.file:
        return

    if MessageAttachment.objects.filter(
            message__author__organization=instance.message.author.organization,
            file=instance.file.name).only('id').exists():
        log.debug('Remaining message attachments ({})...'.format(
            instance.file.name))
        return

    instance.file.delete(save=False)
