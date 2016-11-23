from django.test import TestCase
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient
from rest_framework.reverse import reverse

from munch.apps.users.tests.factories import UserFactory

from ...models import Contact
from ...models import ContactList
from ...models import ContactQueue
from ...models import CollectedContact


class ContactListAPITestCase(TestCase):
    def setUp(self):
        self.api_version = 'v1'
        self.user = UserFactory(groups=['managers'])
        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

    def test_contact_list_default_contact_fields(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 2',
                'contact_fields': [
                    {
                        'name': 'beard_color',
                        'type': 'Char',
                        'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        self.assertEqual(201, response.status_code)
        self.assertEqual(0, response.data['contacts_count'])
        contact_list = ContactList.objects.all().first()
        self.assertEqual(len(contact_list.contact_fields), 1)
        self.assertEqual(contact_list.contact_fields[0].get('type'), 'Char')
        self.assertEqual(contact_list.contact_fields[0].get('required'), True)
        self.assertEqual(
            contact_list.contact_fields[0].get('name'), 'beard_color')

    def test_contact_list_default_empty_contact_fields(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 2',
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        self.assertEqual(201, response.status_code)
        self.assertEqual(0, response.data['contacts_count'])
        contact_list = ContactList.objects.all().first()
        self.assertEqual(
            len(contact_list.contact_fields),
            len(ContactList.DEFAULT_CONTACT_FIELDS))
        for default_field in ContactList.DEFAULT_CONTACT_FIELDS:
            self.assertIn(
                default_field.get('name'),
                [f.get('name') for f in contact_list.contact_fields])

    def test_contact_list_creation(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'has_beard',
                        'type': 'Boolean',
                        'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'},
            format='json')

        self.assertEqual(201, response.status_code)

        url = response.data['url']

        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.data['contacts_count'])

        response = self.client.get(response.data['_links']['contacts']['href'])

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.data['count'])

        self.client.logout()
        another_user = UserFactory(groups=['managers'])
        self.client.login(
            identifier=another_user.identifier, password='password')

        response = self.client.get(url)
        self.assertEqual(403, response.status_code)

    def test_contact_list_double_creation(self):
        """ Same-named contact list """
        ContactList.objects.create(name='Name', author=self.user)

        # same name
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version), {'name': 'Name'})
        self.assertEqual(response.status_code, 400)

    def test_contact_creation(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'has_beard',
                        'type': 'Boolean',
                        'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'},
            format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'has_beard': True}},
            format='json')

        self.assertEqual(201, response.status_code)

        response = self.client.get(url)

        self.assertEqual(1, response.data['contacts_count'])
        mails_response = self.client.get(url + 'contacts/')
        self.assertEqual(mails_response.data['count'], 1)

        response = self.client.get(response.data['_links']['contacts']['href'])

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.data['count'])

        # another list don't get the contacts

        response_list2 = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 2',
                'contact_fields': [
                    {
                        'name': 'has_beard',
                        'type': 'Boolean',
                        'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'},
            format='json')

        url_list2 = response_list2.data['url']
        list2 = self.client.get(url_list2).data
        self.assertEqual(list2['contacts_count'], 0)

        list2_mails = self.client.get(url_list2 + 'contacts/').data
        self.assertEqual(list2_mails['count'], 0)

    def test_bulk_contact_creation(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'has_beard',
                        'type': 'Boolean',
                        'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'},
            format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            data=[
                {
                    'address': 'test1@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': True}},
                {
                    'address': 'test2@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': False}},
                {
                    'address': 'test3@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': False}}],
            format='json')

        self.assertEqual(201, response.status_code)

        response = self.client.get(url)

        self.assertEqual(3, response.data['contacts_count'])

    def test_csv_contact_creation(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'has_beard',
                        'type': 'Boolean',
                        'required': False}],
                'source_type': 'api-test',
                'source_ref': '1'},
            format='json')

        list_url = response.data['url']
        data = [
            {'address': 'test1@example.com', 'properties.has_beard': True},
            {'address': 'test2@example.com', 'properties.has_beard': False},
            {'address': 'test3@example.com', 'properties.has_beard': False}]
        response = self.client.post(
            list_url + 'contacts/', data=data, format='csv')

        self.assertEqual(201, response.status_code)

        response = self.client.get(list_url)

        self.assertEqual(3, response.data['contacts_count'])

        mails_response = self.client.get(list_url + 'contacts/')

        self.assertEqual(len(data), len(mails_response.data['results']))
        # Check if each address are in mails_response.data['results']
        self.assertEqual(
            sorted([c.get('address') for c in data]),
            sorted([c.get('address') for c in mails_response.data['results']]))
        for contact in data:
            # Retrieve contact from mails_response.data['results']
            # based on address
            data_contact = [c for c in mails_response.data['results'] if c.get(
                'address') == contact.get('address')][0]
            self.assertEqual(
                data_contact.get(
                    'properties')['has_beard'], contact.get(
                        'properties.has_beard'))

    def test_filter_properties(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'has_beard',
                        'type': 'Boolean',
                        'required': False}],
                'source_type': 'api-test',
                'source_ref': '1'},
            format='json')

        list_url = response.data['url']

        response = self.client.post(
            list_url + 'contacts/?fields=[has_beard,has_mustache]',
            data=[{'address': 'test1@example.com',
                   'has_beard': 'True',
                   'has_mustache': 'False',
                   'is_hot': 'dunno'}],
            format='csv'
        )
        self.assertEqual(201, response.status_code)

        mails_response = self.client.get(list_url + 'contacts/')
        first_item = mails_response.data['results'][0]
        self.assertEqual(first_item['address'], 'test1@example.com')
        # 'is_hot' should not be included
        self.assertEqual(
            set(first_item['properties']), set(['has_beard']))

    def test_contact_field_add_empty_name(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': '',
                        'type': 'DateTime',
                        'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')
        self.assertEqual(400, response.status_code)

        response = self.client.post(
            '/v1/contacts/lists/',
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': '  ',
                        'type': 'Char',
                        'required': False}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')
        self.assertEqual(400, response.status_code)

    def test_contact_field_add_duplicate_field_name(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_birth',
                        'type': 'DateTime',
                        'required': True},
                    {
                        'name': 'beArd_birtH',
                        'type': 'DateTime',
                        'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')
        self.assertEqual(400, response.status_code)
        self.assertEqual(len(response.data['contact_fields']), 1)
        self.assertIn('beard_birth', response.data['contact_fields'])

        response = self.client.post(
            '/v1/contacts/lists/',
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_birth',
                        'type': 'Char',
                        'required': True},
                    {
                        'name': 'beard_birth',
                        'type': 'Char',
                        'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')
        self.assertEqual(400, response.status_code)
        self.assertEqual(len(response.data['contact_fields']), 1)
        self.assertIn('beard_birth', response.data['contact_fields'])

    def test_contact_field_add_non_required_field(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'beard_birth',
                    'type': 'DateTime',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']
        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'beard_birth': '2015-12-31T10:30:33.000000Z'}},
            format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)
        contact_list = ContactList.objects.all().first()

        response = self.client.put(
            '/{}/contacts/lists/{}/'.format(self.api_version, contact_list.pk),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_birth',
                        'type': 'DateTime',
                        'required': True
                    }, {
                        'name': 'beard_size',
                        'type': 'Float',
                        'required': False}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.get('contact_fields')), 2)

    def test_contact_field_add_required_field(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'beard_birth',
                    'type': 'DateTime',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']
        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'beard_birth': '2015-12-31T10:30:33.000000Z'}},
            format='json')

        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)
        contact_list = ContactList.objects.all().first()

        response = self.client.put(
            '/{}/contacts/lists/{}/'.format(self.api_version, contact_list.pk),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_birth',
                        'type': 'DateTime',
                        'required': True
                    }, {
                        'name': 'beard_size',
                        'type': 'Float',
                        'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            len(response.data.get('contact_fields').get('beard_size')), 1)

    def test_contact_field_add_required_field_trimed(self):
        response = self.client.post(
            '/v1/contacts/lists/',
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_name',
                        'type': 'Char',
                        'required': True
                    }, {
                        'name': 'beard_subname',
                        'type': 'Char',
                        'required': False
                    }],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']
        response = self.client.post(
            '/v1/contacts/',
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'beard_name': '     ', 'beard_subname': '  '}},
            format='json')

        self.assertEqual(400, response.status_code)
        self.assertEqual(Contact.objects.count(), 0)

        response = self.client.post(
            '/v1/contacts/',
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {
                    'beard_name': 'My Beard', 'beard_subname': '  '}},
            format='json')

        self.assertEqual(201, response.status_code)
        self.assertEqual(
            ContactList.objects.all().first().properties.get(
                'beard_subname'), None)

    def test_contact_field_set_existing_field_as_required(self):
        """
            Set a contact_field to required with contact that
            doesn't have value setted. Then, this change can't be done.
        """
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'beard_birth',
                    'type': 'DateTime',
                    'required': False}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']
        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {}},
            format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test2@example.com',
                'contact_list': url,
                'properties': {"beard_birth": "2015-12-31T10:30:33.000000Z"}},
            format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 2)

        contact_list = ContactList.objects.all().first()

        response = self.client.put(
            '/{}/contacts/lists/{}/'.format(self.api_version, contact_list.pk),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_birth',
                        'type': 'DateTime',
                        'required': True
                    }],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            len(response.data.get('contact_fields').get('beard_birth')), 1)
        self.assertEqual(Contact.objects.count(), 2)

    def test_contact_field_set_existing_field_as_required_not_empty(self):
        """
            Set a contact_field to required with all contacts with
            a value setted. Then, this change can be done.
        """
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'beard_birth',
                    'type': 'DateTime',
                    'required': False}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']
        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'beard_birth': '2015-12-31T10:30:33.000000Z'}},
            format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)
        contact_list = ContactList.objects.all().first()

        response = self.client.put(
            '/{}/contacts/lists/{}/'.format(self.api_version, contact_list.pk),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_birth',
                        'type': 'DateTime',
                        'required': True
                    }],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.get('contact_fields')), 1)
        self.assertTrue(response.data.get('contact_fields')[0].get('required'))
        self.assertEqual(
            response.data.get('contact_fields')[0].get('name'), 'beard_birth')
        self.assertEqual(Contact.objects.count(), 1)

    def test_contact_field_remove_field(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_birth',
                        'type': 'DateTime',
                        'required': True},
                    {
                        'name': 'beard_size',
                        'type': 'Float',
                        'required': False}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']
        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {
                    'beard_birth': '2015-12-31T10:30:33.000000Z',
                    'beard_size': 12}},
            format='json')

        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)
        contact_list = ContactList.objects.all().first()

        response = self.client.put(
            '/{}/contacts/lists/{}/'.format(self.api_version, contact_list.pk),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_birth',
                        'type': 'DateTime',
                        'required': True
                    }],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.get('contact_fields')), 1)
        self.assertEqual(
            response.data.get('contact_fields')[0].get('name'), 'beard_birth')
        self.assertIsNone(Contact.objects.first().properties.get('beard_size'))
        self.assertIsNotNone(
            Contact.objects.first().properties.get('beard_birth'))

    def test_contact_field_remove_multiple_fields(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_birth',
                        'type': 'DateTime',
                        'required': True},
                    {
                        'name': 'beard_size',
                        'type': 'Float',
                        'required': True},
                    {
                        'name': 'beard_color',
                        'type': 'Char',
                        'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']
        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {
                    'beard_birth': '2015-12-31T10:30:33.000000Z',
                    'beard_color': 'Blue',
                    'beard_size': 12}},
            format='json')

        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)
        contact_list = ContactList.objects.all().first()

        response = self.client.put(
            '/{}/contacts/lists/{}/'.format(self.api_version, contact_list.pk),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_birth',
                        'type': 'DateTime',
                        'required': True
                    }],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.get('contact_fields')), 1)
        self.assertEqual(
            response.data.get('contact_fields')[0].get('name'), 'beard_birth')
        self.assertIsNone(Contact.objects.first().properties.get('beard_size'))
        self.assertIsNotNone(
            Contact.objects.first().properties.get('beard_birth'))

    def test_contact_field_change_type_to_char(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_birth',
                        'type': 'DateTime',
                        'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']
        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'beard_birth': '2015-12-31T10:30:33.000000Z'}},
            format='json')

        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)
        contact_list = ContactList.objects.all().first()

        response = self.client.put(
            '/{}/contacts/lists/{}/'.format(self.api_version, contact_list.pk),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_birth',
                        'type': 'Char',
                        'required': True
                    }],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.get('contact_fields')), 1)
        self.assertEqual(
            response.data.get('contact_fields')[0].get('name'), 'beard_birth')
        self.assertEqual(
            response.data.get('contact_fields')[0].get('type'), 'Char')
        self.assertIsNotNone(
            Contact.objects.first().properties.get('beard_birth'))

    def test_contact_field_change_type_to_non_char(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_color',
                        'type': 'Char',
                        'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']
        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'beard_color': 'Blue'}},
            format='json')

        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)
        contact_list = ContactList.objects.all().first()

        response = self.client.put(
            '/{}/contacts/lists/{}/'.format(self.api_version, contact_list.pk),
            {
                'name': 'Test list 1',
                'contact_fields': [
                    {
                        'name': 'beard_color',
                        'type': 'Integer',
                        'required': True
                    }],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            len(response.data.get('contact_fields').get('beard_color')), 1)
        self.assertEqual(Contact.objects.count(), 1)

        response = self.client.get(
            '/{}/contacts/lists/{}/'.format(self.api_version, contact_list.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.get('contact_fields')), 1)
        self.assertEqual(
            response.data.get('contact_fields')[0].get('name'), 'beard_color')
        self.assertEqual(
            response.data.get('contact_fields')[0].get('type'), 'Char')


class ContactPropertiesAPITestCase(TestCase):
    def setUp(self):
        self.api_version = 'v1'
        self.user = UserFactory(groups=['managers'])
        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

    def test_contact_field_dropped(self):
        """ Fields not in contact_fields must be dropped """
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Boolean',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {
                    'has_mustache': True,
                    'has_beard': False}
            }, format='json')

        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)
        self.assertNotIn(
            'has_mustache', Contact.objects.first().properties.keys())

    def test_contact_field_required(self):
        """ Required fields must raise ValidationError if not present """
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Boolean',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'has_mustache': True}}, format='json')

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            len(response.data.get('properties').get('has_beard')), 1)
        self.assertEqual(Contact.objects.count(), 0)

    def test_contact_field_boolean_type(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Char',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'has_beard': True}}, format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)

    def test_contact_field_string_type(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Char',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'has_beard': True}}, format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)

    def test_contact_field_integer_type(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Integer',
                    'required': True}, {
                    'name': 'has_mustache',
                    'type': 'Integer',
                    'required': False}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'has_beard': 12}}, format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)

    def test_contact_field_wrong_integer_type(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Integer',
                    'required': True}, {
                    'name': 'has_mustache',
                    'type': 'Integer',
                    'required': False}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']
        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'has_beard': '12aa'}}, format='json')
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            len(response.data.get('properties').get('has_beard')), 1)
        self.assertEqual(Contact.objects.count(), 0)

    def test_contact_field_float_type(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'beard_size',
                    'type': 'Float',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'beard_size': 1.65}}, format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)

    def test_contact_field_wrong_float_type(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'beard_size',
                    'type': 'Float',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'beard_size': True}}, format='json')
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            len(response.data.get('properties').get('beard_size')), 1)
        self.assertEqual(Contact.objects.count(), 0)

    def test_contact_field_date_type(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'beard_age',
                    'type': 'Date',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'beard_age': '2015-12-31'}}, format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)

    def test_contact_field_wrong_date_type(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'beard_age',
                    'type': 'Date',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'beard_age': '2015-003-31'}}, format='json')
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            len(response.data.get('properties').get('beard_age')), 1)
        self.assertEqual(Contact.objects.count(), 0)

    def test_contact_field_datetime_type(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'beard_birth',
                    'type': 'DateTime',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'beard_birth': '2015-12-31T10:30:33.000000Z'}},
            format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test2@example.com',
                'contact_list': url,
                'properties': {'beard_birth': '2015-12-31 10:30:33'}},
            format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 2)

    def test_contact_field_wrong_datetime_type(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'beard_birth',
                    'type': 'DateTime',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {'beard_birth': '2015-13-31'}},
            format='json')
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            len(response.data.get('properties').get('beard_birth')), 1)
        self.assertEqual(Contact.objects.count(), 0)

    def test_contact_field_duplicate_name(self):
        response = self.client.post(
            '/v1/contacts/lists/',
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Char',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/v1/contacts/',
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {
                    'has_beard': 'test',
                    'has_beard ': 'test2'}}, format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)
        self.assertEqual(
            Contact.objects.all().first().properties, {'has_beard': 'test'})

    def test_contact_field_add_empty_property(self):
        response = self.client.post(
            '/v1/contacts/lists/',
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Char',
                    'required': False}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/v1/contacts/',
            {
                'address': 'test@example.com',
                'contact_list': url,
                'properties': {
                    '     ': 'test2',
                    'has_beard': 'test'}}, format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 1)
        self.assertEqual(
            Contact.objects.all().first().properties, {'has_beard': 'test'})


class CollectedContactPropertiesAPITestCase(TestCase):
    def setUp(self):
        self.api_version = 'v1'
        self.user = UserFactory(groups=['managers'])
        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

    def test_contact_field_dropped(self):
        """ Fields not in contact_fields must be dropped """
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'has_beard', 'type': 'Boolean', 'required': True}])
        q.save()
        response = self.client.post(
            reverse(
                'subscription',
                kwargs={'uuid': q.uuid}),
            {
                'address': 'nope@example.org',
                'has_beard': True,
                'has_mustache': True})

        self.assertEqual(201, response.status_code)
        self.assertEqual(CollectedContact.objects.count(), 1)
        self.assertNotIn(
            'has_mustache', CollectedContact.objects.first().properties.keys())

    def test_contact_field_required(self):
        """ Required fields must raise ValidationError if not present """
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'has_beard', 'type': 'Boolean', 'required': True}])
        q.save()

        response = self.client.post(
            reverse(
                'subscription',
                kwargs={'uuid': q.uuid}),
            {
                'address': 'nope@example.org',
                'has_mustache': True})

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            len(response.context[0].get('errors').get('has_beard')), 1)
        self.assertEqual(CollectedContact.objects.count(), 0)

    def test_contact_field_boolean_type(self):
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'has_beard', 'type': 'Char', 'required': True}])
        q.save()

        response = self.client.post(
            reverse(
                'subscription',
                kwargs={'uuid': q.uuid}),
            {
                'address': 'nope@example.org',
                'has_beard': True})
        self.assertEqual(201, response.status_code)
        self.assertEqual(CollectedContact.objects.count(), 1)

    def test_contact_field_string_type(self):
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'has_beard', 'type': 'Char', 'required': True}])
        q.save()

        response = self.client.post(
            reverse(
                'subscription',
                kwargs={'uuid': q.uuid}),
            {
                'address': 'nope@example.org',
                'has_beard': True})

        self.assertEqual(201, response.status_code)
        self.assertEqual(CollectedContact.objects.count(), 1)

    def test_contact_field_integer_type(self):
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'has_beard', 'type': 'Integer', 'required': True},
                {'name': 'has_mustache', 'type': 'Integer', 'required': False}
            ])
        q.save()

        response = self.client.post(
            reverse(
                'subscription',
                kwargs={'uuid': q.uuid}),
            {
                'address': 'nope@example.org',
                'has_beard': 12})

        self.assertEqual(201, response.status_code)
        self.assertEqual(CollectedContact.objects.count(), 1)

    def test_contact_field_wrong_integer_type(self):
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'has_beard', 'type': 'Integer', 'required': True},
                {'name': 'has_mustache', 'type': 'Integer', 'required': False}
            ])
        q.save()

        response = self.client.post(
            reverse(
                'subscription',
                kwargs={'uuid': q.uuid}),
            {
                'address': 'nope@example.org',
                'has_beard': '12aa'})

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            len(response.context[0].get('errors').get('has_beard')), 1)
        self.assertEqual(CollectedContact.objects.count(), 0)

    def test_contact_field_float_type(self):
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'beard_size', 'type': 'Float', 'required': True}
            ])
        q.save()

        response = self.client.post(
            reverse(
                'subscription',
                kwargs={'uuid': q.uuid}),
            {
                'address': 'nope@example.org',
                'beard_size': 1.65})

        self.assertEqual(201, response.status_code)
        self.assertEqual(CollectedContact.objects.count(), 1)

    def test_contact_field_wrong_float_type(self):
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'beard_size', 'type': 'Float', 'required': True}
            ])
        q.save()

        response = self.client.post(
            reverse(
                'subscription',
                kwargs={'uuid': q.uuid}),
            {
                'address': 'nope@example.org',
                'beard_size': True})

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            len(response.context[0].get('errors').get('beard_size')), 1)
        self.assertEqual(CollectedContact.objects.count(), 0)

    def test_contact_field_date_type(self):
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'beard_age', 'type': 'Date', 'required': True}
            ])
        q.save()

        response = self.client.post(
            reverse(
                'subscription',
                kwargs={'uuid': q.uuid}),
            {
                'address': 'nope@example.org',
                'beard_age': '2015-12-31'})
        self.assertEqual(201, response.status_code)
        self.assertEqual(CollectedContact.objects.count(), 1)

    def test_contact_field_wrong_date_type(self):
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'beard_age', 'type': 'Date', 'required': True}
            ])
        q.save()

        response = self.client.post(
            reverse(
                'subscription',
                kwargs={'uuid': q.uuid}),
            {
                'address': 'nope@example.org',
                'beard_age': '2015-003-31'})

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            len(response.context[0].get('errors').get('beard_age')), 1)
        self.assertEqual(CollectedContact.objects.count(), 0)

    def test_contact_field_datetime_type(self):
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'beard_birth', 'type': 'DateTime', 'required': True}
            ])
        q.save()

        response = self.client.post(
            reverse(
                'subscription',
                kwargs={'uuid': q.uuid}),
            {
                'address': 'nope@example.org',
                'beard_birth': '2015-12-31T10:30:33.000000Z'})

        self.assertEqual(201, response.status_code)
        self.assertEqual(CollectedContact.objects.count(), 1)

        response = self.client.post(
            reverse(
                'subscription',
                kwargs={'uuid': q.uuid}),
            {
                'address': 'nope2@example.org',
                'beard_birth': '2015-12-31 10:30:33'})

        self.assertEqual(201, response.status_code)
        self.assertEqual(CollectedContact.objects.count(), 2)

    def test_contact_field_wrong_datetime_type(self):
        q = ContactQueue(
            author=self.user,
            contact_fields=[
                {'name': 'beard_birth', 'type': 'DateTime', 'required': True}])
        q.save()

        response = self.client.post(
            reverse('subscription', kwargs={'uuid': q.uuid}),
            {'address': 'nope@example.org', 'beard_birth': '2015-13-31'})

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            len(response.context[0].get('errors').get('beard_birth')), 1)
        self.assertEqual(CollectedContact.objects.count(), 0)


class ListMergeTest(TestCase):
    def setUp(self):
        self.api_version = 'v1'
        self.user = UserFactory(groups=['managers'])
        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

        self.cl1 = ContactList.objects.create(
            name='self.cl-1', author=self.user)
        self.cl2 = ContactList.objects.create(
            name='self.cl-2', author=self.user)
        self.cl3 = ContactList.objects.create(
            name='self.cl-3', author=self.user)

        Contact.objects.create(address='1@example.com', contact_list=self.cl1)
        Contact.objects.create(address='2@example.com', contact_list=self.cl2)
        Contact.objects.create(address='3@example.com', contact_list=self.cl3)

    def test_contact_list_merge(self):
        response = self.client.post(
            '/{}/contacts/lists/{}/merge/'.format(
                self.api_version, self.cl1.pk),
            [
                'http://testserver' + reverse(
                    '{}:contacts:contactlist-detail'.format(self.api_version),
                    kwargs={'pk': self.cl2.pk}),
                'http://testserver' + reverse(
                    '{}:contacts:contactlist-detail'.format(self.api_version),
                    kwargs={'pk': self.cl3.pk})
            ], format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.cl1.contacts.count(), 3)
        self.assertFalse(ContactList.objects.filter(pk=self.cl2.pk).exists())
        self.assertFalse(ContactList.objects.filter(pk=self.cl3.pk).exists())

    def test_contact_list_merge_bad_list(self):
        response = self.client.post(
            '/{}/contacts/lists/{}/merge/'.format(
                self.api_version, self.cl1.pk), ['http://example.com/foo/bar'],
            format='json')
        self.assertEqual(response.status_code, 400)

    def test_contact_list_merge_not_my_list(self):
        self.another_user = UserFactory(groups=['users'])
        self.client.login(
            identifier=self.another_user.identifier, password='password')
        response = self.client.post(
            '/{}/contacts/lists/{}/merge/'.format(
                self.api_version, self.cl1.pk), [
                    'http://testserver' + reverse(
                        '{}:contacts:contactlist-detail'.format(
                            self.api_version),
                        kwargs={'pk': self.cl2.pk})],
            format='json')
        self.assertEqual(response.status_code, 400)

    def test_contact_list_merge_no_list(self):
        self.another_user = UserFactory(groups=['users'])
        self.client.login(
            identifier=self.another_user.identifier, password='password')
        response = self.client.post(
            '/{}/contacts/lists/{}/merge/'.format(
                self.api_version, self.cl1.pk), [], format='json')
        self.assertEqual(response.status_code, 200)

    def test_contact_list_merge_with_itself(self):
        response = self.client.post(
            '/{}/contacts/lists/{}/merge/'.format(
                self.api_version, self.cl1.pk),
            ['/{}/contacts/lists/{}/'.format(self.api_version, self.cl1.pk)],
            format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.cl1.contacts.count(), 1)

    def test_contact_list_merge_no_delete_perm(self):
        # alter permissions to remove the right to DELETE lists
        moderators = Group.objects.get(name='managers')

        delete_perms = Permission.objects.filter(
            codename__startswith='delete_', codename__endswith='_contactlist')
        for perm in delete_perms:
            moderators.permissions.remove(perm)
        self.client.logout()
        self.client.login(identifier=self.user.identifier, password='password')

        response = self.client.post(
            '/{}/contacts/lists/{}/merge/'.format(
                self.api_version, self.cl1.pk),
            [
                'http://testserver' + reverse(
                    '{}:contacts:contactlist-detail'.format(self.api_version),
                    kwargs={'pk': self.cl2.pk})], format='json')
        self.assertEqual(response.status_code, 400)

    def test_contact_list_merge_doubles(self):
        # It already exists in self.cl1
        double_contact = Contact.objects.create(
            address='1@example.com', contact_list=self.cl2)
        response = self.client.post(
            '/{}/contacts/lists/{}/merge/'.format(
                self.api_version, self.cl1.pk),
            ['http://testserver' + reverse(
                '{}:contacts:contactlist-detail'.format(self.api_version),
                kwargs={'pk': self.cl2.pk})],
            format='json')
        self.assertEqual(self.cl1.contacts.count(), 2)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContactList.objects.filter(pk=self.cl2.pk).exists())
        self.assertFalse(Contact.objects.filter(pk=double_contact.pk).exists())


class ContactBulkAPITestCase(TestCase):
    def setUp(self):
        self.api_version = 'v1'
        self.user = UserFactory(groups=['managers'])
        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

    def test_two_valid_contacts(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Boolean',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            [
                {
                    'address': 'test01@example.com',
                    'contact_list': url,
                    'properties': {
                        'has_mustache': True,
                        'has_beard': False}
                },
                {
                    'address': 'test02@example.com',
                    'contact_list': url,
                    'properties': {
                        'has_mustache': True,
                        'has_beard': False}
                },
            ], format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 2)

    def test_one_contact_not_valid(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Boolean',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            [
                {
                    'address': 'test01@example.com',
                    'contact_list': url,
                    'properties': {
                        'has_mustache': True,
                        'has_beard': False}
                },
                {
                    'address': 'test02@example.com',
                    'contact_list': url,
                    'properties': {
                        'has_mustache': True}
                },
            ], format='json')

        self.assertEqual(400, response.status_code)
        self.assertIn(
            'test02@example.com', response.json()['validation_errors'].keys())
        self.assertEqual(response.json()['no_address'], '0')
        self.assertEqual(response.json()['duplicates'], [])
        self.assertEqual(Contact.objects.count(), 0)

    def test_duplicate_contacts(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Boolean',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            [
                {
                    'address': 'test01@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': False}
                },
                {
                    'address': 'test02@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': False}
                },
                {
                    'address': 'test02@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': False}
                },
            ], format='json')

        self.assertEqual(400, response.status_code)
        self.assertIn('test02@example.com', response.json()['duplicates'])
        self.assertEqual(response.json()['no_address'], '0')
        self.assertEqual(response.json()['validation_errors'], {})
        self.assertEqual(Contact.objects.count(), 0)

    def test_invalid_and_duplicate_and_missing_email(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Boolean',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            [
                {
                    'address': 'test01@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': False}
                },
                {
                    'address': 'test02@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': False}
                },
                {
                    'address': 'test02@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': False}
                },
                {
                    'address': 'test03@example.com',
                    'contact_list': url,
                    'properties': {'has_mustach': False}
                },
                {
                    'contact_list': url,
                    'properties': {'has_beard': False}
                },
                {
                    'address': '_no_addr',
                    'contact_list': url,
                    'properties': {'has_beard': False}
                }
            ], format='json')

        self.assertEqual(400, response.status_code)
        self.assertIn('test03@example.com', response.json()[
            'validation_errors'])
        self.assertIn('test02@example.com', response.json()['duplicates'])
        self.assertEqual(response.json()['no_address'], '1')
        self.assertEqual(Contact.objects.count(), 0)

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            [
                {
                    'address': 'test01@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': True}
                },
                {
                    'address': 'dadadaada??',
                    'contact_list': url,
                    'properties': {'has_beard': False}
                }
            ], format='json')

        self.assertEqual(400, response.status_code)
        self.assertIn('dadadaada??', response.json()['validation_errors'])
        self.assertEqual(Contact.objects.count(), 0)

    def test_add_contacts_via_bulk(self):
        response = self.client.post(
            '/{}/contacts/lists/'.format(self.api_version),
            {
                'name': 'Test list 1',
                'contact_fields': [{
                    'name': 'has_beard',
                    'type': 'Boolean',
                    'required': True}],
                'source_type': 'api-test',
                'source_ref': '1'}, format='json')

        url = response.data['url']

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            [
                {
                    'address': 'test01@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': False}
                },
                {
                    'address': 'test02@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': False}
                }
            ], format='json')

        self.assertEqual(201, response.status_code)
        self.assertEqual(Contact.objects.count(), 2)

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            [
                {
                    'address': 'test01@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': True}
                },
                {
                    'address': 'dadadaada??',
                    'contact_list': url,
                    'properties': {'has_beard': False}
                }
            ], format='json')

        self.assertEqual(400, response.status_code)
        self.assertEqual(Contact.objects.count(), 2)

        response = self.client.post(
            '/{}/contacts/'.format(self.api_version),
            [
                {
                    'address': 'test01@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': True}
                },
                {
                    'address': 'test03@example.com',
                    'contact_list': url,
                    'properties': {'has_beard': False}
                }
            ], format='json')

        self.assertEqual(400, response.status_code)
        self.assertIn('test01@example.com', response.json()[
            'validation_errors'])
        self.assertEqual(Contact.objects.count(), 2)
