import re
import unittest
from datetime import date
from datetime import timedelta

from django.core import mail
from django.urls import reverse
from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from django.test.utils import override_settings
from libfaketime import fake_time
from rest_framework.test import APIClient

from .. import tasks
from ..models import Contact
from ..models import ContactList
from ..models import ContactQueue
from ..models import CollectedContact
from ..models import ContactListPolicy
from ..models import ContactListPolicyAttribution
from ..models import ContactQueuePolicyAttribution

from munch.apps.users.tests.factories import UserFactory


bounce = {
    'Auto-Submitted': 'auto-replied',
    'Content-Type': 'multipart/report; report-type=delivery-status;\n\t'
    'boundary="A10868308A6BB.1438776632/mail.example.com"',
    'Date': 'Wed,  5 Aug 2015 14:10:32 +0200 (CEST)',
    'Delivered-To': '{bounce}',
    'From': 'MAILER-DAEMON@example.com (Mail Delivery System)',
    'MIME-Version': '1.0',
    'Message-Id': '<20150805121032.E77C18308A6BC@mail.example.com>',
    'Received': 'by mail.example.com (Postfix)\n\tid E77C18308A6BC;'
    ' Wed,  5 Aug 2015 14:10:32 +0200 (CEST)',
    'Return-Path': '<MAILER-DAEMON>',
    'Subject': 'Undelivered Mail Returned to Sender',
    'To': '{bounce}'}


URL_REGEX = re.compile('https?://[^\s]+')


@override_settings(
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_ALWAYS_EAGER=True,
    BROKER_BACKEND='memory')
class ContactQueuesTestCase(TestCase):
    fixtures = ['generic_policies']

    def setUp(self):
        self.user = UserFactory(groups=['managers'])
        # Remove subscription email
        mail.outbox = []
        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

    def test_subscription_without_policies(self):
        q = ContactQueue(author=self.user)
        q.save()

        contact = CollectedContact(
            contact_queue=q, address='nope@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        self.assertEqual(CollectedContact.OK, contact.status)
        self.assertEqual(0, len(mail.outbox))

    def test_single_policy_subscription(self):
        q = ContactQueue(author=self.user)
        q.save()

        qa = ContactQueuePolicyAttribution(
            contact_queue=q,
            policy=ContactListPolicy.objects.get(name='DoubleOptIn'))
        qa.save()

        contact = CollectedContact(
            contact_queue=q, address='nope@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        self.assertEqual(CollectedContact.PENDING, contact.status)
        self.assertEqual(1, len(mail.outbox))

    @unittest.skip('Disabled temporarily to allow deploy. FIXME !!!')
    def test_bounce_backend(self):
        q = ContactQueue(author=self.user)
        q.save()

        qa = ContactQueuePolicyAttribution(
            contact_queue=q,
            policy=ContactListPolicy.objects.get(name='BounceCheck'))
        qa.save()

        contact = CollectedContact(
            contact_queue=q, address='nope@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        self.assertEqual(1, len(mail.outbox))

        bounce_address = mail.outbox.pop().message().get('Return-Path')

        # sending bounce task
        tasks.handle_bounce(
            {k: v.format(bounce=bounce_address) for k, v in bounce.items()})

        contact.refresh_from_db()
        self.assertEqual(CollectedContact.BOUNCED, contact.status)

        contact = CollectedContact(
            contact_queue=q, address='truemail@example.com',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        with fake_time(timezone.now() + timedelta(hours=5)):
            tasks.handle_bounce_expirations()

        contact.refresh_from_db()
        self.assertEqual(CollectedContact.OK, contact.status)

        contact = CollectedContact(
            contact_queue=q, address='truemail2@example.com',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        with fake_time(timezone.now() + timedelta(minutes=5)):
            tasks.handle_bounce_expirations()

        contact.refresh_from_db()
        self.assertEqual(
            CollectedContact.PENDING, contact.status,
            'Bounce-check hasn’t expired yet, so the contact should not be OK')

    def test_double_opt_in_backend(self):
        q = ContactQueue(author=self.user)
        q.save()

        qa = ContactQueuePolicyAttribution(
            contact_queue=q,
            policy=ContactListPolicy.objects.get(name='DoubleOptIn'))
        qa.save()

        contact = CollectedContact(
            contact_queue=q, address='nope@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        self.assertEqual(1, len(mail.outbox))
        confirmation_msg = mail.outbox.pop().body
        url = URL_REGEX.search(confirmation_msg).group().replace(
            settings.APPLICATION_URL, '')
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)

        contact.refresh_from_db()
        self.assertEqual(CollectedContact.OK, contact.status)

        contact = CollectedContact(
            contact_queue=q, address='nope2@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        with fake_time(timezone.now() + timedelta(days=8)):
            tasks.handle_opt_ins_expirations()

        contact.refresh_from_db()
        self.assertEqual(CollectedContact.EXPIRED, contact.status)

        contact = CollectedContact(
            contact_queue=q, address='nope3@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        with fake_time(timezone.now() + timedelta(days=2)):
            tasks.handle_opt_ins_expirations()

        contact.refresh_from_db()
        self.assertEqual(CollectedContact.PENDING, contact.status)

    @unittest.skip('Disabled temporarily to allow deploy. FIXME !!!')
    def test_multiple_backends(self):
        q = ContactQueue(author=self.user)
        q.save()

        qa1 = ContactQueuePolicyAttribution(
            contact_queue=q,
            policy=ContactListPolicy.objects.get(name='DoubleOptIn'))
        qa1.save()

        qa2 = ContactQueuePolicyAttribution(
            contact_queue=q,
            policy=ContactListPolicy.objects.get(name='BounceCheck'))
        qa2.save()

        contact = CollectedContact(
            contact_queue=q, address='nope1@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        self.assertEqual(CollectedContact.PENDING, contact.status)
        self.assertEqual(
            1, len(mail.outbox),
            'Using DoubleOptIn and BounceCheck should only send 1 mail')

        bounce_address = mail.outbox.pop().message().get('Return-Path')

        # sending bounce task
        tasks.handle_bounce(
            {k: v.format(bounce=bounce_address) for k, v in bounce.items()})

        contact.refresh_from_db()
        self.assertEqual(CollectedContact.BOUNCED, contact.status)

        contact = CollectedContact(
            contact_queue=q, address='nope2@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        confirmation_msg = mail.outbox.pop().body
        url = URL_REGEX.search(confirmation_msg).group().replace(
            settings.APPLICATION_URL, '')
        self.client.get(url)

        contact.refresh_from_db()
        self.assertEqual(
            CollectedContact.OK, contact.status,
            'Contact should be validated if confirmation link is '
            'clicked, even if the bounce hasn’t expired')

        contact = CollectedContact(
            contact_queue=q, address='nope3@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        with fake_time(timezone.now() + timedelta(hours=5)):
            tasks.handle_bounce_expirations()

        contact.refresh_from_db()
        self.assertEqual(
            CollectedContact.PENDING, contact.status,
            'Bounce expiration should not set contact status to '
            '“ok” if DoubleOptIn is set')

    @unittest.skip('Disabled temporarily to allow deploy. FIXME !!!')
    def test_failed_expiration(self):
        q = ContactQueue(author=self.user)
        q.save()

        qa = ContactQueuePolicyAttribution(
            contact_queue=q,
            policy=ContactListPolicy.objects.get(name='DoubleOptIn'))
        qa.save()

        contact = CollectedContact(
            contact_queue=q, address='nope@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        with fake_time(timezone.now() + timedelta(days=8)):
            tasks.handle_opt_ins_expirations()

        with fake_time(timezone.now() + timedelta(days=15)):
            tasks.handle_failed_expirations()

        # Long-time expired contact should be deleted
        self.assertRaises(contact.DoesNotExist, contact.refresh_from_db)

        contact = CollectedContact(
            contact_queue=q, address='nope@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        q = ContactQueue(author=self.user)
        q.save()

        qa = ContactQueuePolicyAttribution(
            contact_queue=q,
            policy=ContactListPolicy.objects.get(name='BounceCheck'))
        qa.save()

        contact = CollectedContact(
            contact_queue=q, address='bounce@nope',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        bounce_address = mail.outbox.pop().message().get('Return-Path')

        # sending bounce task
        tasks.handle_bounce(
            {k: v.format(bounce=bounce_address) for k, v in bounce.items()})

        with fake_time(timezone.now() + timedelta(days=15)):
            tasks.handle_failed_expirations()

        # Long-time bounced contact should be deleted
        self.assertRaises(contact.DoesNotExist, contact.refresh_from_db)

        contact = CollectedContact(
            contact_queue=q, address='ok@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        contact.status = CollectedContact.CONSUMED
        contact.save()

        with fake_time(timezone.now() + timedelta(days=15)):
            tasks.handle_consumed_contacts_expirations()

        # Long-time consumed contact should be deleted
        self.assertRaises(contact.DoesNotExist, contact.refresh_from_db)

    def test_http_subscription(self):
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'name', 'type': 'Char'},
                {'name': 'age', 'type': 'Integer'}])
        q.save()

        response = self.client.post(
            reverse('subscription', kwargs={'uuid': q.uuid}),
            {'address': 'yep@example.org', 'name': 'John Doe', 'age': 42})
        self.assertEqual(response.status_code, 201)

        try:
            contact = q.collected_contacts.get(address='yep@example.org')
        except CollectedContact.DoesNotExist:
            self.fail('The contact should have been saved')

        self.assertEqual(2, len(contact.properties))

        self.client.post(
            reverse('subscription', kwargs={'uuid': q.uuid}),
            {
                'address': 'nope@example.org',
                'name': 'John Doe', 'age': 'won’t tell'})

        self.assertRaises(
            CollectedContact.DoesNotExist,
            q.collected_contacts.get,
            address='nope@example.org')

    def test_queue_creation(self):
        types = self.client.get('/v1/contacts/queues/fields/')
        self.assertEqual(200, types.status_code)
        types = types.data
        self.assertTrue(len(types) >= 3)
        self.assertIn('Char', types)
        self.assertIn('Boolean', types)
        self.assertIn('Date', types)

        policies = self.client.get('/v1/contacts/policies/')
        self.assertEqual(200, policies.status_code)
        policies = policies.data['results']
        self.assertTrue(len(policies) >= 2)

        response = self.client.post(
            '/v1/contacts/queues/',
            {'policies': [policies[0]['url'], policies[1]['url']],
             "contact_fields": [
                 {"name": "prop1", "type": "Char", "required": True},
                 {"name": "prop2", "type": "Boolean", "required": False},
                 {"name": "prop3", "type": "Date", "required": False}
            ]}, format='json')

        queue = response.data
        self.assertEqual(201, response.status_code)
        self.assertEqual(queue['contact_fields'], [
            {"name": "prop1", "type": "Char", "required": True},
            {"name": "prop2", "type": "Boolean", "required": False},
            {"name": "prop3", "type": "Date", "required": False}])
        self.assertEqual(
            queue['policies'], [policies[0]['url'], policies[1]['url']])

        # Test that it appears in listing

        list_response = self.client.get('/v1/contacts/queues/')
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data['results'], [queue])

        # Test that it appears in detail view

        detail_response = self.client.get(queue['url'])
        self.assertEqual(detail_response.data, queue)

        # testing contact add

        contact = self.client.post(
            queue['subscription'], {
                'address': 'nope@example.org',
                'prop1': 'test', 'prop2': True, 'prop3': date.today()})

        self.assertEqual(201, contact.status_code)

        try:
            contact = CollectedContact.objects.get(address='nope@example.org')
        except CollectedContact.DoesNotExist:
            self.fail('Contact should have been written')

        self.assertEqual('127.0.0.1', contact.subscription_ip)

        # should trigger an error the second time

        response = self.client.post(
            queue['subscription'], {
                'address': 'nope@example.org',
                'prop1': 'test', 'prop2': True, 'prop3': timezone.now()})

        self.assertEqual(400, response.status_code)

    def test_queue_creation_bad_proptype(self):
        response = self.client.post(
            '/v1/contacts/queues/',
            {'contact_fields': [
                {'type': 'Char', 'name': 'prop1'},
                {'type': 'Foo', 'name': 'prop2'}],
             'policies': []},
            format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Foo', response.content.decode('utf-8'))

    def test_queue_update(self):
        q = ContactQueue(
            author=self.user,
            properties={'name': 'Char', 'age': 'Integer'})
        q.save()
        ContactQueuePolicyAttribution.objects.create(
            contact_queue=q,
            policy=ContactListPolicy.objects.get(name='DoubleOptIn'))
        response = self.client.put(
            '/v1/contacts/queues/{}/'.format(q.pk), {
                'contact_fields': [
                    {'type': 'Char', 'name': 'lala1'},
                ],
                'policies': ['/v1/contacts/policies/1/',
                             '/v1/contacts/policies/2/']
            }, format='json')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data['policies'],
            [
                'http://testserver/v1/contacts/policies/1/',
                'http://testserver/v1/contacts/policies/2/'])

    def test_queue_consumption(self):
        q = ContactQueue(author=self.user)
        q.save()

        contact1 = CollectedContact(
            contact_queue=q, address='ok@nope', subscription_ip='127.0.0.1')
        contact1.save()
        contact1.apply_policies()

        contact2 = CollectedContact(
            contact_queue=q, address='pending@nope',
            subscription_ip='127.0.0.1')
        contact2.save()

        consumed = self.client.post(
            '/v1/contacts/queues/{}/consume/'.format(q.pk))

        self.assertEqual(200, consumed.status_code)
        self.assertEqual(1, len(consumed.data['contacts']))
        self.assertEqual('ok@nope', consumed.data['contacts'][0]['address'])

        consumed = self.client.post(
            '/v1/contacts/queues/{}/consume/'.format(q.pk))

        self.assertEqual(0, len(consumed.data['contacts']))

        consumed = self.client.post(
            '/v1/contacts/queues/{}/consume/?status=pending'.format(q.pk))

        self.assertEqual(1, len(consumed.data['contacts']))

        contact2.status = CollectedContact.OK
        contact2.save()

        consumed = self.client.post(
            '/v1/contacts/queues/{}/consume/'.format(q.pk))

        self.assertEqual(1, len(consumed.data['contacts']))

        consumed = self.client.post(
            '/v1/contacts/queues/{}/consume/?status=pending'.format(q.pk))

        self.assertEqual(0, len(consumed.data['contacts']))

        consumed = self.client.post(
            '/v1/contacts/queues/{}/consume/?status=consumed'.format(q.pk))

        self.assertEqual(2, len(consumed.data['contacts']))


@override_settings(
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_ALWAYS_EAGER=True,
    BROKER_BACKEND='memory')
class ContactListTestCase(TestCase):
    fixtures = ['generic_policies']

    def setUp(self):
        self.user = UserFactory()
        # Remove subscription email
        mail.outbox = []
        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

    def test_single_policy_subscription(self):
        contact_list = ContactList(author=self.user)
        contact_list.save()

        policy_attribution = ContactListPolicyAttribution(
            contact_list=contact_list,
            policy=ContactListPolicy.objects.get(name='DoubleOptIn'))
        policy_attribution.save()

        contact = Contact(
            contact_list=contact_list,
            address='nope@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        self.assertEqual(Contact.PENDING, contact.status)
        self.assertEqual(1, len(mail.outbox))

    @unittest.skip('Disabled temporarily to allow deploy. FIXME !!!')
    def test_bounce_backend(self):
        contact_list = ContactList(author=self.user)
        contact_list.save()

        policy_attribution = ContactListPolicyAttribution(
            contact_list=contact_list,
            policy=ContactListPolicy.objects.get(name='BounceCheck'))
        policy_attribution.save()

        contact = Contact(
            contact_list=contact_list,
            address='nope@nope', subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        self.assertEqual(1, len(mail.outbox))

        bounce_address = mail.outbox.pop().message().get('Return-Path')

        # sending bounce task
        tasks.handle_bounce(
            {k: v.format(bounce=bounce_address) for k, v in bounce.items()})

        contact.refresh_from_db()
        self.assertEqual(Contact.BOUNCED, contact.status)

        contact = Contact(
            contact_list=contact_list, address='truemail@example.com',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        with fake_time(timezone.now() + timedelta(hours=10)):
            tasks.handle_bounce_expirations()

        contact.refresh_from_db()
        self.assertEqual(Contact.OK, contact.status)

        contact = Contact(
            contact_list=contact_list, address='truemail2@example.com',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        with fake_time(timezone.now() + timedelta(minutes=5)):
            tasks.handle_bounce_expirations()

        contact.refresh_from_db()
        self.assertEqual(
            Contact.PENDING, contact.status,
            'Bounce-check hasn’t expired yet, so the contact should not be OK')

    def test_double_opt_in_backend(self):
        contact_list = ContactList(author=self.user)
        contact_list.save()

        cl_queue_policy = ContactListPolicyAttribution(
            contact_list=contact_list,
            policy=ContactListPolicy.objects.get(name='DoubleOptIn'))
        cl_queue_policy.save()

        contact = Contact(
            contact_list=contact_list,
            address='nope@nope',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        self.assertEqual(1, len(mail.outbox))
        confirmation_msg = mail.outbox.pop().body
        url = URL_REGEX.search(confirmation_msg).group().replace(
            settings.APPLICATION_URL, '')
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)

        contact.refresh_from_db()
        self.assertEqual(Contact.OK, contact.status)

        contact = Contact(
            contact_list=contact_list,
            address='nope2@nope',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        with fake_time(timezone.now() + timedelta(days=8)):
            tasks.handle_opt_ins_expirations()

        contact.refresh_from_db()
        self.assertEqual(Contact.EXPIRED, contact.status)

        contact = Contact(
            contact_list=contact_list,
            address='nope3@nope',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        with fake_time(timezone.now() + timedelta(days=2)):
            tasks.handle_opt_ins_expirations()

        contact.refresh_from_db()
        self.assertEqual(Contact.PENDING, contact.status)

    @unittest.skip('Disabled temporarily to allow deploy. FIXME !!!')
    def test_multiple_backends(self):
        contact_list = ContactList(author=self.user)
        contact_list.save()

        list_attribution_1 = ContactListPolicyAttribution(
            contact_list=contact_list,
            policy=ContactListPolicy.objects.get(name='DoubleOptIn'))
        list_attribution_1.save()

        list_attribution_2 = ContactListPolicyAttribution(
            contact_list=contact_list,
            policy=ContactListPolicy.objects.get(name='BounceCheck'))
        list_attribution_2.save()

        contact = Contact(
            contact_list=contact_list,
            address='nope1@nope',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        self.assertEqual(Contact.PENDING, contact.status)
        self.assertEqual(
            1, len(mail.outbox),
            'Using DoubleOptIn and BounceCheck should only send 1 mail')

        bounce_address = mail.outbox.pop().message().get('Return-Path')

        # sending bounce task
        tasks.handle_bounce({k: v.format(bounce=bounce_address)
                             for k, v in bounce.items()})

        contact.refresh_from_db()
        self.assertEqual(Contact.BOUNCED, contact.status)

        contact = Contact(
            contact_list=contact_list,
            address='nope2@nope',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        confirmation_msg = mail.outbox.pop().body
        url = URL_REGEX.search(confirmation_msg).group().replace(
            settings.APPLICATION_URL, '')
        self.client.get(url)

        contact.refresh_from_db()
        self.assertEqual(
            Contact.OK, contact.status,
            'Contact should be validated if confirmation link is '
            'clicked, even if the bounce hasn’t expired')

        contact = Contact(
            contact_list=contact_list,
            address='nope3@nope',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        with fake_time(timezone.now() + timedelta(hours=5)):
            tasks.handle_bounce_expirations()

        contact.refresh_from_db()
        self.assertEqual(
            Contact.PENDING, contact.status,
            'Bounce expiration should not set contact status to '
            '“ok” if DoubleOptIn is set')

    @unittest.skip('Disabled temporarily to allow deploy. FIXME !!!')
    def test_failed_expiration(self):
        contact_list = ContactList(name="list_1", author=self.user)
        contact_list.save()

        list_attribution = ContactListPolicyAttribution(
            contact_list=contact_list,
            policy=ContactListPolicy.objects.get(name='DoubleOptIn'))
        list_attribution.save()

        contact = Contact(
            contact_list=contact_list,
            address='nope@nope',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        with fake_time(timezone.now() + timedelta(days=8)):
            tasks.handle_opt_ins_expirations()

        with fake_time(timezone.now() + timedelta(days=15)):
            tasks.handle_failed_expirations()

        # Long-time expired contact should be deleted
        self.assertRaises(contact.DoesNotExist, contact.refresh_from_db)

        contact = Contact(
            contact_list=contact_list,
            address='nope@nope',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        contact_list = ContactList(name="list_2", author=self.user)
        contact_list.save()

        list_attribution = ContactListPolicyAttribution(
            contact_list=contact_list,
            policy=ContactListPolicy.objects.get(name='BounceCheck'))
        list_attribution.save()

        contact = Contact(
            contact_list=contact_list,
            address='bounce@nope',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()
        bounce_address = mail.outbox.pop().message().get('Return-Path')

        # sending bounce task
        tasks.handle_bounce(
            {k: v.format(bounce=bounce_address) for k, v in bounce.items()})

        with fake_time(timezone.now() + timedelta(days=15)):
            tasks.handle_failed_expirations()

        # Long-time bounced contact should be deleted
        self.assertRaises(contact.DoesNotExist, contact.refresh_from_db)

        contact = Contact(
            contact_list=contact_list,
            address='ok@nope',
            subscription_ip='127.0.0.1')
        contact.save()
        contact.apply_policies()

        contact.status = Contact.CONSUMED
        contact.save()

        with fake_time(timezone.now() + timedelta(days=15)):
            tasks.handle_consumed_contacts_expirations()

        try:
            contact.refresh_from_db()
        except contact.DoesNotExist:
            self.fail(
                'Long-time consumed contact should not be deleted because '
                'contacts are never consumed compared to collected contacts.')

    def test_http_subscription(self):
        contact_list = ContactList(
            author=self.user,
            contact_fields=[
                {'name': 'name', 'type': 'Char'},
                {'name': 'age', 'type': 'Integer'}])
        contact_list.save()

        response = self.client.post(
            reverse('subscription', kwargs={'uuid': contact_list.uuid}),
            {
                'address': 'yep@example.org',
                'name': 'John Doe',
                'age': 42})
        self.assertEqual(response.status_code, 201)

        try:
            contact = contact_list.contacts.get(address='yep@example.org')
        except Contact.DoesNotExist:
            self.fail('The contact should have been saved')

        self.assertEqual(2, len(contact.properties))

        self.client.post(
            reverse('subscription', kwargs={'uuid': contact_list.uuid}),
            {
                'address': 'nope@example.org',
                'name': 'John Doe',
                'age': 'won’t tell'})

        self.assertRaises(
            Contact.DoesNotExist,
            contact_list.contacts.get, address='nope@example.org')
