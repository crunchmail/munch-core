import logging

from django.core.management.base import BaseCommand

from munch.core.mail.utils import extract_domain

from ...models import Mail
from ...models import MailStatus

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete message ids. Theses emails won't be send."

    def add_arguments(self, parser):
        parser.add_argument('identifier', nargs='+', type=str)

    def handle(self, *args, **options):
        for identifier in options['identifier']:
            try:
                mail = Mail.objects.get(identifier=identifier)
                MailStatus.objects.create(
                    destination_domain=extract_domain(mail.recipient),
                    mail=mail, status=MailStatus.DELETED)
                self.stdout.write(self.style.SUCCESS(
                    "* {} (pk:{}) ignored".format(identifier, mail.pk)))
            except Mail.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    "* {} doesn't exist (ignored)".format(identifier)))
                exit(1)
