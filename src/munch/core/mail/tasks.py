import logging

from celery import task

log = logging.getLogger(__name__)


@task
def purge_raw_mail():
    from .models import RawMail
    kwargs = {}
    for related_object in RawMail._meta.related_objects:
        accessor_name = related_object.field.related_query_name()
        kwargs.update({'{}__isnull'.format(accessor_name): True})
        log.info('Scanning all orphans RawMail.{}...'.format(accessor_name))

    count, _ = RawMail.objects.filter(**kwargs).only('id').delete()
    log.info('RawMail deleted: {} ({})'.format(count, kwargs))
