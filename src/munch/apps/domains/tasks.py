from datetime import timedelta

from celery import task
from django.utils import timezone
from celery.utils.log import get_task_logger

from .models import SendingDomain
from .fields import DomainCheckField

log = get_task_logger(__name__)


@task
def run_domains_validation(statuses):
    """
        Task that iterate over all domains with specified statuses
        in order to re-check them.
    """
    for field in ['dkim', 'app_domain']:
        if statuses == [DomainCheckField.OK]:
            filters = {'{}_status'.format(field): DomainCheckField.OK}
        else:
            filters = {
                '{}_status__in'.format(field): statuses,
                '{}_status_date__gt'.format(
                    field): timezone.now() - timedelta(days=2)}

        qs = SendingDomain.objects.filter(**filters).only('id')
        log.info(
            'Running sending domain "{}" validations for {} domain(s) '
            'with statuses: {}...'.format(field, statuses, qs.count()))
        for domain in qs:
            validate_sending_domain_field.apply_async([domain.id, field])


@task
def validate_sending_domain_field(domain_id, field):
    domain = SendingDomain.objects.get(id=domain_id)
    previous_status = getattr(domain, '{}_status'.format(field))
    getattr(domain, 'validate_{}'.format(field))()
    if getattr(domain, '{}_status'.format(field)) != previous_status:
        setattr(domain, '{}_status_date'.format(field), timezone.now())
        domain.save()
