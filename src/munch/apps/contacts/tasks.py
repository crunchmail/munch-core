import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from celery.decorators import periodic_task
from celery.utils.log import get_task_logger

from .models import Contact
from .models import AbstractContact
from .models import CollectedContact

from munch.core.utils.tasks import AutoRetryTask


log = get_task_logger(__name__)


@periodic_task(run_every=timedelta(minutes=1))
def handle_opt_ins_expirations():
    """
    Set contacts and collected contacts to Expired status when expiration
    time passed without being validated (status: OK).
    Both contacts and collected contacts are concerned.
    """
    doi_expiration = timezone.now() - settings.CONTACTS['EXPIRATIONS'][
        'contact_queues:double-opt-in']
    contacts = CollectedContact.objects.filter(
        status=AbstractContact.PENDING,
        update_date__lt=doi_expiration,
        contact_queue__policies__name='DoubleOptIn')
    log.info(
        'Updating {} collected contact(s) to Expired'.format(contacts.count()))
    contacts.update(status=AbstractContact.EXPIRED)

    doi_expiration = timezone.now() - settings.CONTACTS['EXPIRATIONS'][
        'contact_lists:double-opt-in']
    contacts = Contact.objects.filter(
        status=AbstractContact.PENDING,
        update_date__lt=doi_expiration,
        contact_list__policies__name='DoubleOptIn')
    log.info('Updating {} contact(s) to Expired'.format(contacts.count()))
    contacts.update(status=AbstractContact.EXPIRED)


@periodic_task(run_every=timedelta(minutes=1))
def handle_bounce_expirations():
    """
    Set contacts and collected contacts to OK status when expiration time
    passed without being bounced.
    Both contacts and collected contacts are concerned.
    """
    bc_expiration = timezone.now() - settings.CONTACTS['EXPIRATIONS'][
        'contact_queues:bounce-check']
    contacts = CollectedContact.objects.exclude(
        contact_queue__policies__name='DoubleOptIn').filter(
            status=AbstractContact.PENDING,
            update_date__lt=bc_expiration,
            contact_queue__policies__name='BounceCheck')
    # We don’t want Double-Opt-In contacts here, because the “OK” status should
    # only be given by the confirmation link
    log.info('Accepting {} collected contact(s) that didn’t bounce'
             .format(contacts.count()))
    contacts.update(status=AbstractContact.OK)

    bc_expiration = timezone.now() - settings.CONTACTS['EXPIRATIONS'][
        'contact_lists:bounce-check']
    contacts = Contact.objects.exclude(
        contact_list__policies__name='DoubleOptIn').filter(
            status=AbstractContact.PENDING,
            update_date__lt=bc_expiration,
            contact_list__policies__name='BounceCheck')
    # We don’t want Double-Opt-In contacts here, because the “OK” status should
    # only be given by the confirmation link
    log.info('Accepting {} contact(s) that didn’t bounce'
             .format(contacts.count()))
    contacts.update(status=AbstractContact.OK)


@periodic_task(run_every=timedelta(minutes=1))
def handle_consumed_contacts_expirations():
    """
    Delete consumed contacts after an expiration time.
    Only collected contacts can be consumed.
    """
    filters = {
        'status': AbstractContact.CONSUMED,
        'update_date__lt': timezone.now() - settings.CONTACTS['EXPIRATIONS'][
            'contact_queues:consumed_lifetime']}
    contacts = CollectedContact.objects.filter(**filters)
    log.info('Deleting {} collected contact(s) that have been consumed'.format(
        contacts.count()))
    contacts.delete()


@periodic_task(run_every=timedelta(minutes=1))
def handle_failed_expirations():
    """
    Delete expired and bounced contacts after an expiration time.
    Both contacts and collected contacts can have these statuses.
    """
    filters = {
        'status__in': (AbstractContact.BOUNCED, AbstractContact.EXPIRED),
        'update_date__lt': None}

    filters.update({
        'update_date__lt': timezone.now() - settings.CONTACTS['EXPIRATIONS'][
            'contact_queues:failed_lifetime']})
    contacts = CollectedContact.objects.filter(**filters)
    log.info('Deleting {} collected contact(s) that bounced or expired'.format(
        contacts.count()))
    contacts.delete()

    filters.update({
        'update_date__lt': timezone.now() - settings.CONTACTS['EXPIRATIONS'][
            'contact_lists:failed_lifetime']})
    contacts = Contact.objects.filter(**filters)
    log.info('Deleting {} contact(s) that bounced or expired'.format(
        contacts.count()))
    contacts.delete()


@periodic_task(run_every=timedelta(minutes=1))
class handle_bounce(AutoRetryTask):
    def safe_run(self, msg):
        regexp = re.compile(r'^subscription-bounce\+(?P<uuid>[^@]+)@')
        match = regexp.match(msg['To'])
        if match:
            uuid = match.groups()[0]
            contact = None
            filters = {'uuid': uuid, 'status': AbstractContact.PENDING}
            try:
                contact = CollectedContact.objects.get(**filters)
            except CollectedContact.DoesNotExist:
                try:
                    contact = Contact.objects.get(**filters)
                except Contact.DoesNotExist:
                    pass

            if not contact:
                return

            contact.status = CollectedContact.BOUNCED
            contact.save()
            log.info(
                'Contact subscription {} is bounced'.format(contact.address))
