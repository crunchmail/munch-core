from django.core.management.base import BaseCommand

from ...models import TrackRecord


class Command(BaseCommand):
    help = "Build tracking cache"

    def handle(self, *args, **options):
        count = TrackRecord.clear_cache()
        self.stdout.write('TrackingRecord deleted: {}'.format(count))
        count = 0
        for track_record in TrackRecord.objects.all():
            count += track_record.cache()
        self.stdout.write('TrackingRecord cached: {}'.format(count))
