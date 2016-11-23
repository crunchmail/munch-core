from django.db.models.signals import pre_save
from django.db.models.signals import post_save

from munch.core.mail import backend

from .models import MailStatus

# MailStatus
pre_save.connect(backend.pre_save_mailstatus_signal, sender=MailStatus)
post_save.connect(backend.post_save_mailstatus_signal, sender=MailStatus)
