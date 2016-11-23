import uuid
from urllib.parse import urljoin

from django.db import models
from django.db.models import Count
from django.urls import reverse
from django.conf import settings
from django.contrib.postgres import fields
from django.contrib.postgres.fields import JSONField

from munch.core.utils.models import AbstractOwnedModel
from munch.apps.users.models import MunchUser
from munch.apps.campaigns.validators import slug_regex_validator

from . import backends
from .validators import properties_schema_validator

PROP_TYPES = ('Char', 'Integer', 'Date', 'DateTime', 'Boolean', 'Float')


class ContactListPolicy(models.Model):
    name = models.CharField('nom', max_length=100)
    description = models.TextField('description')

    def get_backend(self):
        return getattr(backends, self.name)

    def __str__(self):
        return self.name

    def apply(self, item, policies_list):
        """
        Applies the current policy to the item (basically, a Contact).
        The backend could take knowledge of the full policies list, in order to
        adapt its behaviour.
        """
        self.get_backend()().apply(item, policies_list)

    class Meta:
        verbose_name = 'politique de file'
        verbose_name_plural = 'politiques de files'


class ContactQueuePolicyAttribution(models.Model):
    policy = models.ForeignKey(ContactListPolicy)
    contact_queue = models.ForeignKey('contacts.ContactQueue')

    class Meta:
        unique_together = (('policy', 'contact_queue', ), )


class ContactListPolicyAttribution(models.Model):
    policy = models.ForeignKey(ContactListPolicy)
    contact_list = models.ForeignKey('contacts.ContactList')

    class Meta:
        unique_together = (('policy', 'contact_list', ), )


class AbstractContact(AbstractOwnedModel):
    PENDING = 'pending'
    BOUNCED = 'bounced'
    EXPIRED = 'expired'
    OK = 'ok'
    CONSUMED = 'consumed'

    properties = fields.HStoreField('propriétés', default={})
    address = models.EmailField('adresse e-mail')
    creation_date = models.DateTimeField('date de création', auto_now_add=True)
    update_date = models.DateTimeField('date de modification', auto_now=True)
    uuid = models.UUIDField(editable=False, default=uuid.uuid4)
    status = models.CharField(
        'statut', max_length=50, choices=(
            (PENDING, 'en attente'),
            (BOUNCED, 'échec bounce'),
            (EXPIRED, 'expiré'),
            (OK, 'ok'),
            (CONSUMED, 'consommé')), default=PENDING)
    subscription_ip = models.GenericIPAddressField(
        'adresse IP d’envoi', default='127.0.0.1')

    class Meta(AbstractOwnedModel.Meta):
        abstract = True
        verbose_name = 'contact'

    def apply_policies(self):
        """
        Executes each policy registered with the ContactList.
        """
        if getattr(self, self.contact_list_path).policies.count() == 0:
            self.status = self.OK
            self.save()
        else:
            policies = getattr(self, self.contact_list_path).policies.all()
            policies_names = [p.name for p in policies]
            for policy in policies:
                policy.apply(self, policies_names)


class Contact(AbstractContact):
    contact_list = models.ForeignKey(
        'ContactList', related_name='contacts')

    owner_path = 'contact_list__author__organization'
    author_path = 'contact_list__author'
    contact_list_path = 'contact_list'

    class Meta:
        unique_together = (('contact_list', 'address'), )

    def __str__(self):
        return self.address


class CollectedContact(AbstractContact):
    contact_queue = models.ForeignKey(
        'ContactQueue', related_name='collected_contacts')

    owner_path = 'contact_queue__author__organization'
    author_path = 'contact_queue__author'
    contact_list_path = 'contact_queue'

    class Meta:
        verbose_name = 'adresse collectée'
        verbose_name_plural = 'adresses collectées'
        unique_together = (('contact_queue', 'address'), )


class AbstractContactList(AbstractOwnedModel):
    author = models.ForeignKey(MunchUser, verbose_name='auteur')
    properties = fields.HStoreField('propriétés', default={})
    source_type = models.CharField(
        blank=True, max_length=100, validators=[slug_regex_validator])
    source_ref = models.CharField(blank=True, max_length=200)
    uuid = models.UUIDField(editable=False, default=uuid.uuid4)

    owner_path = 'author__organization'
    author_path = 'author'

    class Meta:
        abstract = True

    @property
    def subscription(self):
        return urljoin(
            settings.APPLICATION_URL.strip('/'),
            reverse('subscription', kwargs={'uuid': self.uuid}))


class ContactList(AbstractContactList):
    DEFAULT_CONTACT_FIELDS = [
        {'name': 'Prénom', 'type': 'Char', 'required': False},
        {'name': 'Nom', 'type': 'Char', 'required': False}]
    name = models.CharField('nom', max_length=100)
    contact_fields = JSONField(
        'champs des contacts', default=DEFAULT_CONTACT_FIELDS,
        validators=[properties_schema_validator])
    policies = models.ManyToManyField(
        ContactListPolicy,
        verbose_name='politiques de la file',
        through=ContactListPolicyAttribution)

    class Meta:
        verbose_name = 'liste de contacts'
        verbose_name_plural = 'listes de contacts'
        unique_together = (('author', 'name'), )

    def __str__(self):
        return self.name

    def contacts_count(self):
        return self.contacts.count()


class ContactQueue(AbstractContactList):
    DEFAULT_CONTACT_FIELDS = []
    contact_fields = JSONField(
        'champs des contacts', default=DEFAULT_CONTACT_FIELDS,
        validators=[properties_schema_validator])
    policies = models.ManyToManyField(
        ContactListPolicy,
        verbose_name='politiques de la file',
        through=ContactQueuePolicyAttribution)

    def contacts_count(self):
        """Returns a dict with contact count for each status in the queue.
        """
        return {c['status']: c['count'] for c in
                self.collected_contacts.values('status').annotate(
                    count=Count('status'))}

    def consume(self, status=AbstractContact.OK):
        contacts = self.collected_contacts.filter(status=status)
        if status == AbstractContact.OK:
            contacts_list = list(contacts)
            contacts.update(status=AbstractContact.CONSUMED)
            contacts = contacts_list
            # because QuerySet.update() seems to consume the list
        return contacts
