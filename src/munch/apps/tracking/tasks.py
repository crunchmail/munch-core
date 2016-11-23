import logging

from celery import task

from .models import TrackRecord

log = logging.getLogger(__name__)


@task
def create_track_record(**kwargs):
    try:
        TrackRecord.objects.create(**kwargs)
    except:
        log.error('Error while tracking an event', exc_info=True)
