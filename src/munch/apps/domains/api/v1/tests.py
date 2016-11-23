from django.test import TestCase
from django.conf import settings
from rest_framework.test import APIClient
from faker import Factory as FakerFactory

from munch.apps.users.tests.factories import UserFactory
from munch.apps.users.tests.factories import OrganizationFactory

from ...models import SendingDomain

faker = FakerFactory.create()


class SendingDomainAPITestCase(TestCase):
    def setUp(self):
        self.api_prefix = 'v1'
        self.organization = OrganizationFactory()
        self.admin = UserFactory(
            groups=['administrators'], organization=self.organization)
        self.manager = UserFactory(
            groups=['managers'], organization=self.organization)
        self.user = UserFactory(
            groups=['users'], organization=self.organization)

        self.client = APIClient()
        self.client.login(
            identifier=self.admin.identifier, password='password')

    def test_non_admin_cannot_create_sending_domain(self):
        data = {'name': 'example.com'}

        self.client.login(
            identifier=self.manager.identifier, password='password')
        response = self.client.post(
            '/{}/domains/'.format(self.api_prefix), data, format='json')
        self.assertEqual(403, response.status_code)

        self.client.login(
            identifier=self.user.identifier, password='password')
        response = self.client.post(
            '/{}/domains/'.format(self.api_prefix), data, format='json')
        self.assertEqual(403, response.status_code)

        self.client.login(
            identifier=self.admin.identifier, password='password')
        response = self.client.post(
            '/{}/domains/'.format(self.api_prefix), data, format='json')
        self.assertEqual(201, response.status_code)

    def test_non_admin_add_alt_organizations(self):
        organization = OrganizationFactory(parent=self.admin.organization)

        parent_url = self.client.get(
            '/{}/me/'.format(self.api_prefix)).data.get('organization')
        children = self.client.get(
            self.client.get(parent_url).data.get('_links')['children']['href'])


        data = {
            'name': 'example.com',
            'alt_organizations': [children.data[0]['url']]}

        self.client.login(
            identifier=self.manager.identifier, password='password')

        response = self.client.post(
            '/{}/domains/'.format(self.api_prefix), data, format='json')
        self.assertEqual(403, response.status_code)

        self.client.login(
            identifier=self.user.identifier, password='password')

        response = self.client.post(
            '/{}/domains/'.format(self.api_prefix), data, format='json')
        self.assertEqual(403, response.status_code)


    def test_admin_add_alt_organizations(self):
        organization = OrganizationFactory(parent=self.admin.organization)

        parent_url = self.client.get(
            '/{}/me/'.format(self.api_prefix)).data.get('organization')
        children = self.client.get(
            self.client.get(parent_url).data.get('_links')['children']['href'])


        data = {
            'name': 'example.com',
            'alt_organizations': [children.data[0]['url']]}

        self.client.login(
            identifier=self.admin.identifier, password='password')

        response = self.client.post(
            '/{}/domains/'.format(self.api_prefix), data, format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(
            data['alt_organizations'], response.json()['alt_organizations'])

    def test_non_admin_list_domains(self):
        self.client.login(identifier=self.user.identifier, password='password')
        response = self.client.get('/{}/domains/'.format(self.api_prefix))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.get('results')), 0)

        organization = OrganizationFactory(parent=self.admin.organization)

        parent_url = self.client.get(
            '/{}/me/'.format(self.api_prefix)).data.get('organization')
        children = self.client.get(
            self.client.get(parent_url).data.get('_links')['children']['href'])


        data = {
            'name': 'example.com',
            'alt_organizations': [children.data[0]['url']]}

        self.client.login(
            identifier=self.admin.identifier, password='password')

        self.client.post(
            '/{}/domains/'.format(self.api_prefix), data, format='json')

        self.client.login(identifier=self.user.identifier, password='password')
        response = self.client.get('/{}/domains/'.format(self.api_prefix))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.get('results')), 1)
        self.assertEqual(
            response.data.get('results')[0]['name'], 'example.com')

    def test_admin_add_non_owned_organization(self):
        user = UserFactory(groups=['administrators'])

        self.client.login(identifier=user.identifier, password='password')
        parent_url = self.client.get(
            '/{}/me/'.format(self.api_prefix)).data.get('organization')


        data = {
            'name': 'another-example.com', 'alt_organizations': [parent_url]}

        self.client.login(
            identifier=self.admin.identifier, password='password')

        response = self.client.post(
            '/{}/domains/'.format(self.api_prefix), data, format='json')
        self.assertEqual(400, response.status_code)
        self.assertEqual(len(data['alt_organizations']), 1)
        self.assertEqual(SendingDomain.objects.count(), 0)
