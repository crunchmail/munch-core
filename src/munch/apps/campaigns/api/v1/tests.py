from django.test import TestCase
from django.conf import settings
from rest_framework.test import APIClient
from faker import Factory as FakerFactory

from munch.apps.users.tests.factories import UserFactory

from ...models import Mail
from ...models import Message
from ...tests.factories import MailFactory
from ...tests.factories import MessageFactory

faker = FakerFactory.create()


class MessageAPITestCase(TestCase):
    def setUp(self):
        self.api_prefix = 'v1'
        self.user = UserFactory(groups=['managers'])
        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

        self.html = '<html>{}</html>'.format(
            settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])

    def test_read_only_fields(self):
        response = self.client.post(
            '/{}/messages/'.format(self.api_prefix),
            {
                'name': 'test message',
                'subject': 'subject',
                'html': self.html,
                'sender_email': 'foo@bar.com',
                'sender_name': 'foo'}, format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Message.objects.count(), 1)

        url = response.data['url']

        response = self.client.put(
            url,
            {
                'name': 'test message',
                'subject': 'subject modified',
                'sender_email': 'foo@bar.com',
                'send_date': '1990-12-01',
                'sender_name': 'foo'}, format='json')
        self.assertEqual(response.json()['send_date'], None)
        self.assertEqual(response.json()['subject'], 'subject modified')

    def test_create_message(self):
        response = self.client.post(
            '/{}/messages/'.format(self.api_prefix),
            {
                'name': 'test message',
                'subject': 'subject',
                'html': self.html,
                'sender_email': 'foo@bar.com',
                'sender_name': 'foo'}, format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Message.objects.count(), 1)

        url = response.data['url']

        response = self.client.post(
            '/{}/recipients/'.format(self.api_prefix),
            {'message': url, 'to': 'foo@bar.com'}, format='json')
        response = self.client.patch(
            url, {'status': 'sending'}, format='json')
        self.assertEqual(response.json()['status'], 'sending')


class MailAPITestCase(TestCase):
    def setUp(self):
        self.api_prefix = 'v1'
        self.user = UserFactory(groups=['managers'])
        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

        self.html = '<html>{}</html>'.format(
            settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])

        self.message = MessageFactory(author=self.user)

    def test_empty_delete(self):
        MailFactory(message=self.message)
        MailFactory(message=self.message)
        response = self.client.delete(
            '/{}/recipients/'.format(self.api_prefix),
            [], format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Mail.objects.count(), 2)

        response = self.client.delete(
            '/{}/recipients/'.format(self.api_prefix),
            '', format='json')
        self.assertEqual(response.status_code, 400)

    def test_not_found_id(self):
        MailFactory(message=self.message)
        response = self.client.delete(
            '/{}/recipients/'.format(self.api_prefix),
            ['http://localhost:8000/v1/recipients/2'], format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Mail.objects.count(), 1)

    def test_delete_one(self):
        mail = MailFactory(message=self.message)
        response = self.client.get('/{}/recipients/{}/'.format(
            self.api_prefix, mail.id))
        response = self.client.delete(
            '/{}/recipients/'.format(self.api_prefix),
            [response.data['url']], format='json')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Mail.objects.count(), 0)

    def test_delete_multiple(self):
        urls = []

        mail = MailFactory(message=self.message)
        response = self.client.get('/{}/recipients/{}/'.format(
            self.api_prefix, mail.id))
        urls.append(response.data['url'])
        mail = MailFactory(message=self.message)
        response = self.client.get('/{}/recipients/{}/'.format(
            self.api_prefix, mail.id))
        urls.append(response.data['url'])

        self.assertEqual(Mail.objects.count(), 2)
        response = self.client.delete(
            '/{}/recipients/'.format(self.api_prefix), urls, format='json')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Mail.objects.count(), 0)

    def test_delete_multiple_with_one_not_found(self):
        urls = ['http://localhost:8000/v1/recipients/12321321/']

        mail = MailFactory(message=self.message)
        response = self.client.get('/{}/recipients/{}/'.format(
            self.api_prefix, mail.id))
        urls.append(response.data['url'])
        mail = MailFactory(message=self.message)
        response = self.client.get('/{}/recipients/{}/'.format(
            self.api_prefix, mail.id))
        urls.append(response.data['url'])

        self.assertEqual(Mail.objects.count(), 2)
        response = self.client.delete(
            '/{}/recipients/'.format(self.api_prefix), urls, format='json')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Mail.objects.count(), 0)

    def test_delete_not_owned(self):
        user = UserFactory(groups=['managers'])
        message = MessageFactory(author=user)
        mail = MailFactory(message=message)

        self.client.login(identifier=user.identifier, password='password')
        response = self.client.get('/{}/recipients/{}/'.format(
            self.api_prefix, mail.id))

        self.client.login(identifier=self.user.identifier, password='password')
        response = self.client.delete(
            '/{}/recipients/'.format(self.api_prefix),
            [response.data['url']], format='json')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Mail.objects.count(), 1)


class MailBulkAPITestCase(TestCase):
    def setUp(self):
        self.api_prefix = 'v1'
        self.user = UserFactory(groups=['managers'])
        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

        self.html = '<html>{}</html>'.format(
            settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])

        self.message = MessageFactory(author=self.user)
        self.message_url = self.client.get('/{}/messages/{}/'.format(
            self.api_prefix, self.message.id)).data['url']

    def test_bad_format(self):
        email = faker.email()

        data = [
            [{'message': self.message_url, 'to': email}],
            {'message': self.message_url, 'to': ''}
        ]
        response = self.client.post(
            '/{}/recipients/'.format(self.api_prefix), data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['duplicates'], [])
        self.assertEqual(response.json()['validation_errors'], {})
        self.assertEqual(response.json()['no_address'], 2)
        self.assertEqual(len(response.json()['results']), 0)

        data = [
            'Jambon',
            {'message': self.message_url, 'to': email}
        ]
        response = self.client.post(
            '/{}/recipients/'.format(self.api_prefix), data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['duplicates'], [])
        self.assertEqual(response.json()['validation_errors'], {})
        self.assertEqual(response.json()['no_address'], 1)
        self.assertEqual(len(response.json()['results']), 0)

    def test_missing_address(self):
        email = faker.email()

        data = [
            {'message': self.message_url, 'to': email},
            {'message': self.message_url, 'to': ''}
        ]
        response = self.client.post(
            '/{}/recipients/'.format(self.api_prefix), data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['duplicates'], [])
        self.assertEqual(response.json()['validation_errors'], {})
        self.assertEqual(response.json()['no_address'], 1)
        self.assertEqual(len(response.json()['results']), 1)

        recipient = response.json()['results'][0]
        self.assertEqual(recipient['to'], email)
        self.assertEqual(Mail.objects.count(), 1)

    def test_duplicates(self):
        email = faker.email()

        data = [
            {'message': self.message_url, 'to': faker.email()},
            {'message': self.message_url, 'to': email},
            {'message': self.message_url, 'to': email}
        ]
        response = self.client.post(
            '/{}/recipients/'.format(self.api_prefix), data, format='json')
        self.assertEqual(response.json()['duplicates'], [email])
        self.assertEqual(len(response.json()['results']), 2)
        self.assertEqual(Mail.objects.count(), 2)

    def test_unicity(self):
        email = faker.email()
        MailFactory(recipient=email, message=self.message)

        data = [
            {'message': self.message_url, 'to': faker.email()},
            {'message': self.message_url, 'to': email}
        ]
        response = self.client.post(
            '/{}/recipients/'.format(self.api_prefix), data, format='json')
        self.assertEqual(response.json()['duplicates'], [])
        self.assertEqual(len(response.json()['results']), 1)
        self.assertIn(email, response.json()['validation_errors'])
        self.assertEqual(
            response.json()['validation_errors'][email],
            ['This address is already attached to this message.'])
        self.assertEqual(Mail.objects.count(), 2)

    def test_all_recipients_must_have_same_message(self):
        message = MessageFactory(author=self.user)
        message_url = self.client.get('/{}/messages/{}/'.format(
            self.api_prefix, message.id)).data['url']

        data = [
            {'message': self.message_url, 'to': faker.email()},
            {'message': message_url, 'to': faker.email()}
        ]
        response = self.client.post(
            '/{}/recipients/'.format(self.api_prefix), data, format='json')
        self.assertEqual(response.json()['results'], [])
        self.assertEqual(
            response.json()['non_field_errors'],
             ['Every object must have same message'])
        self.assertEqual(Mail.objects.count(), 0)

    def test_another_error(self):
        email = faker.email()
        data = [{'message': 'http://dadada', 'to': email}]

        response = self.client.post(
            '/{}/recipients/'.format(self.api_prefix), data, format='json')
        self.assertEqual(response.json()['duplicates'], [])
        self.assertIn(email, response.json()['validation_errors'])
        self.assertIn('message', response.json()['validation_errors'][email])
