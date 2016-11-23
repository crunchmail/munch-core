import logging

from django.core.management.base import BaseCommand

from ...models import Mail

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'List message statuses based on X-CM-Message-Id'

    def add_arguments(self, parser):
        parser.add_argument('identifier', nargs='+', type=str)
        parser.add_argument(
            '--with-headers',
            dest='with_headers',
            action='store_true')

    def handle(self, *args, **options):
        for mail in Mail.objects.filter(
                identifier__in=options['identifier']):
            self.stdout.write(self.style.SUCCESS(
                '* {} (pk:{}) (author:{})'.format(
                    mail.identifier, mail.pk, mail.author)))
            if options['with_headers']:
                print('├────────────── Headers ──────────────')
                for k, v in mail.headers.items():
                    print('│ {}: {}'.format(k, v))
            print('├────────────── Statuses ──────────────')
            for status in mail.mailstatus_set.all().order_by('creation_date'):
                print('├─ {}: {} by {} ({}) to {}'.format(
                    status.creation_date,
                    status.status,
                    status.source_ip,
                    status.source_hostname or '<missing>',
                    status.destination_domain or '<missing>'))
            print('└──────────────────────────────────────')
