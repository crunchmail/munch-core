from django.test import TestCase
from rest_framework.test import APIClient
from faker import Factory as FakerFactory

from ...models import MunchUser
from ...models import Organization
from ...models import APIApplication
from ...models import SmtpApplication
from ...tests.factories import UserFactory
from ...tests.factories import OrganizationFactory
from ...tests.factories import APIApplicationFactory
from ...tests.factories import SmtpApplicationFactory

faker = FakerFactory.create()


class APIApplicationAPITestCase(TestCase):
    def setUp(self):
        self.api_prefix = 'v1'
        self.user = UserFactory(groups=['managers'])
        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

    def test_create_api_application(self):
        response = self.client.post(
            '/{}/applications/api/'.format(self.api_prefix),
            {'identifier': 'api-foo'}, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(APIApplication.objects.count(), 1)

    def test_read_only_secret(self):
        response = self.client.post(
            '/{}/applications/api/'.format(self.api_prefix),
            {'identifier': 'api-foo', 'secret': '1'}, format='json')
        self.assertNotEqual(response.data['secret'], '1')

        response = self.client.patch(
            response.data['url'], {'secret': '1'}, format='json')
        self.assertNotEqual(response.data['secret'], '1')

    def test_regen_secret(self):
        response = self.client.post(
            '/{}/applications/api/'.format(self.api_prefix),
            {'identifier': 'api-foo'}, format='json')

        self.assertEqual(response.data['identifier'], 'api-foo')
        self.assertTrue(response.data['secret'])

        secret = response.data['secret']
        application = APIApplication.objects.all().first()

        response = self.client.post(
            '/{}/applications/api/{}/regen_secret/'.format(
                self.api_prefix, application.pk))

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data, secret)

    def test_unique_identifier(self):
        response = self.client.post(
            '/{}/applications/api/'.format(self.api_prefix),
            {'identifier': 'api-foo'}, format='json')

        response = self.client.post(
            '/{}/applications/api/'.format(self.api_prefix),
            {'identifier': 'api-foo'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(APIApplication.objects.count(), 1)
        self.assertIn('non_field_errors', response.json())

    def test_update_identifier(self):
        response = self.client.post(
            '/{}/applications/api/'.format(self.api_prefix),
            {'identifier': 'api-foo'}, format='json')

        response = self.client.put(
            response.json().get('url'),
            {'identifier': 'api-foo-updated'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('identifier'), 'api-foo-updated')

    def test_permissions_not_manager_same_organization(self):
        # Create an API application as manager
        response = self.client.post(
            '/{}/applications/api/'.format(self.api_prefix),
            {'identifier': 'api'}, format='json')
        url = response.json().get('url')

        # Test a simple user
        user = UserFactory(
            groups=['users'], organization=self.user.organization)
        self.client.login(identifier=user.identifier, password='password')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.get(
            '/{}/applications/api/'.format(self.api_prefix))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            '/{}/applications/api/'.format(self.api_prefix),
            {'identifier': 'api-foo'}, format='json')
        self.assertEqual(response.status_code, 403)

        # Test a collaborator
        collaborator = UserFactory(
            groups=['collaborators'], organization=self.user.organization)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.client.login(
            identifier=collaborator.identifier, password='password')
        response = self.client.get(
            '/{}/applications/api/'.format(self.api_prefix))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            '/{}/applications/api/'.format(self.api_prefix),
            {'identifier': 'api-foo'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_permissions_another_organization(self):
        # Create an API application with first organization
        response = self.client.post(
            '/{}/applications/api/'.format(self.api_prefix),
            {'identifier': 'api-foo'}, format='json')
        url = response.json().get('url')

        # Create another manager for another organization
        another_manager = UserFactory(groups=['managers'])
        self.client.login(
            identifier=another_manager.identifier, password='password')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        response = self.client.get(
            '/{}/applications/api/'.format(self.api_prefix))
        self.assertEqual(response.json().get('count'), 0)


class SmtpApplicationAPITestCase(TestCase):
    def setUp(self):
        self.api_prefix = 'v1'
        self.user = UserFactory(groups=['managers'])
        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

    def test_create_smtp_application(self):
        response = self.client.post(
            '/{}/applications/smtp/'.format(self.api_prefix),
            {'identifier': 'smtp-foo'}, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(SmtpApplication.objects.count(), 1)
        self.assertTrue(response.json().get('username'))
        self.assertTrue(response.json().get('secret'))

    def test_read_only_credentials(self):
        response = self.client.post(
            '/{}/applications/smtp/'.format(self.api_prefix),
            {'identifier': 'smtp-foo', 'secret': '1', 'username': 'jambon'},
            format='json')
        self.assertNotEqual(response.data['secret'], '1')
        self.assertNotEqual(response.data['username'], 'jambon')

        response = self.client.patch(
            response.data['url'],
            {'secret': '1', 'username': 'jambon'}, format='json')
        self.assertNotEqual(response.data['secret'], '1')
        self.assertNotEqual(response.data['username'], 'jambon')

    def test_regen_credentials(self):
        response = self.client.post(
            '/{}/applications/smtp/'.format(self.api_prefix),
            {'identifier': 'smtp-foo'}, format='json')

        self.assertEqual(response.data['identifier'], 'smtp-foo')
        self.assertTrue(response.data['secret'])
        self.assertTrue(response.data['username'])

        secret = response.data['secret']
        username = response.data['username']

        application = SmtpApplication.objects.all().first()

        response = self.client.post(
            '/{}/applications/smtp/{}/regen_credentials/'.format(
                self.api_prefix, application.pk))

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json().get('secret'), secret)
        self.assertNotEqual(response.json().get('username'), username)

    def test_unique_identifier(self):
        response = self.client.post(
            '/{}/applications/smtp/'.format(self.api_prefix),
            {'identifier': 'smtp-foo'}, format='json')

        response = self.client.post(
            '/{}/applications/smtp/'.format(self.api_prefix),
            {'identifier': 'smtp-foo'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(SmtpApplication.objects.count(), 1)
        self.assertIn('non_field_errors', response.json())

    def test_update_identifier(self):
        response = self.client.post(
            '/{}/applications/smtp/'.format(self.api_prefix),
            {'identifier': 'smtp-foo'}, format='json')

        response = self.client.put(
            response.json().get('url'),
            {'identifier': 'smtp-foo-updated'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('identifier'), 'smtp-foo-updated')

    def test_permissions_not_manager_same_organization(self):
        # Create an API application as manager
        response = self.client.post(
            '/{}/applications/smtp/'.format(self.api_prefix),
            {'identifier': 'smtp'}, format='json')
        url = response.json().get('url')

        # Test a simple user
        user = UserFactory(
            groups=['users'], organization=self.user.organization)
        self.client.login(identifier=user.identifier, password='password')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.get(
            '/{}/applications/smtp/'.format(self.api_prefix))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            '/{}/applications/smtp/'.format(self.api_prefix),
            {'identifier': 'smtp-foo'}, format='json')
        self.assertEqual(response.status_code, 403)

        # Test a collaborator
        collaborator = UserFactory(
            groups=['collaborators'], organization=self.user.organization)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.client.login(
            identifier=collaborator.identifier, password='password')
        response = self.client.get(
            '/{}/applications/smtp/'.format(self.api_prefix))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            '/{}/applications/smtp/'.format(self.api_prefix),
            {'identifier': 'smtp-foo'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_permissions_another_organization(self):
        # Create an API application with first organization
        response = self.client.post(
            '/{}/applications/smtp/'.format(self.api_prefix),
            {'identifier': 'smtp-foo'}, format='json')
        url = response.json().get('url')

        # Create another manager for another organization
        another_manager = UserFactory(groups=['managers'])
        self.client.login(
            identifier=another_manager.identifier, password='password')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        response = self.client.get(
            '/{}/applications/smtp/'.format(self.api_prefix))
        self.assertEqual(response.json().get('count'), 0)


class OrganizationAPITestCase(TestCase):
    def setUp(self):
        self.api_prefix = 'v1'
        self.administrator = UserFactory(groups=['administrators'])
        self.manager = UserFactory(
            groups=['managers'], organization=self.administrator.organization)
        self.user = UserFactory(
            groups=['users'], organization=self.administrator.organization)

        self.client = APIClient()
        self.client.login(
            identifier=self.administrator.identifier, password='password')

        self.url = '/{}/organizations/'.format(self.api_prefix)

    def test_can_only_see_mine_organization(self):
        user = UserFactory(groups=['administrators'])
        self.assertEqual(Organization.objects.count(), 2)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 1)

        self.client.login(
            identifier=self.manager.identifier, password='password')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 1)

        self.client.login(
            identifier=self.user.identifier, password='password')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 1)

        self.client.login(identifier=user.identifier, password='password')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 1)

    def test_nobody_can_create_non_child_organization(self):
        data = {'name': 'name', 'contact_email': 'contact@example.com' }

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Organization.objects.count(), 1)

        self.client.login(
            identifier=self.manager.identifier, password='password')
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Organization.objects.count(), 1)

        self.client.login(
            identifier=self.user.identifier, password='password')
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Organization.objects.count(), 1)

    def test_only_administrator_can_create_child_organization(self):
        data = {
            'name': 'name',
            'parent': self.client.get(self.url).json()['results'][0]['url'],
            'contact_email': 'contact@example.com' }

        # Manager
        self.client.login(
            identifier=self.manager.identifier, password='password')
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Organization.objects.count(), 1)

        # User
        self.client.login(
            identifier=self.user.identifier, password='password')
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Organization.objects.count(), 1)

        # Administrator
        self.client.login(
            identifier=self.administrator.identifier, password='password')
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Organization.objects.count(), 2)

    def test_cannot_create_child_of_not_owned_organization(self):
        user = UserFactory(groups=['administrators'])
        self.assertEqual(Organization.objects.count(), 2)

        self.client.login(identifier=user.identifier, password='password')
        data = {
            'name': 'name',
            'parent': self.client.get(self.url).json()['results'][0]['url'],
            'contact_email': 'contact@example.com' }

        self.client.login(
            identifier=self.administrator.identifier, password='password')
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Organization.objects.count(), 2)
        self.assertIn('parent', response.json())

    def test_cannot_add_child_on_child_organization(self):
        data = {
            'name': 'name',
            'parent': self.client.get(self.url).json()['results'][0]['url'],
            'contact_email': 'contact@example.com' }

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Organization.objects.count(), 2)

        data = {
            'name': 'name',
            'parent': response.json()['url'],
            'contact_email': 'contact@example.com' }

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('parent', response.json())
        self.assertEqual(Organization.objects.count(), 2)

    def test_only_adminstrator_can_see_children_organizations(self):
        data = {
            'name': 'name',
            'parent': self.client.get(self.url).json()['results'][0]['url'],
            'contact_email': 'contact@example.com' }

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Organization.objects.count(), 2)

        organization = self.client.get(self.url).json()['results'][0]
        response = self.client.get(organization['_links']['children']['href'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

        response = self.client.get(
            response.json()[0]['_links']['children']['href'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)


class InvitationAPITestCase(TestCase):
    def setUp(self):
        self.api_prefix = 'v1'

        self.administrator = UserFactory(groups=['administrators'])
        self.user = UserFactory(
            groups=['users'], organization=self.administrator.organization)

        self.client = APIClient()
        self.client.login(
            identifier=self.administrator.identifier, password='password')

    def test_simple_invitation(self):
        organization_url = '/{}/organizations/{}/'.format(
            self.api_prefix, self.administrator.organization_id)
        invite_user_url = self.client.get(organization_url).json()[
            '_links']['invite_user']['href']
        data = {"identifier": faker.safe_email()}
        resp = self.client.post(invite_user_url, data)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["identifier"], data['identifier'])
        self.assertEqual(self.administrator.organization.users.count(), 3)
        self.assertFalse(MunchUser.objects.filter(
            identifier=data['identifier']).first().is_active)

    def test_already_used_identifier(self):
        organization_url = '/{}/organizations/{}/'.format(
            self.api_prefix, self.administrator.organization_id)
        invite_user_url = self.client.get(organization_url).json()[
            '_links']['invite_user']['href']
        data = {"identifier": self.user.identifier}
        resp = self.client.post(invite_user_url, data)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.administrator.organization.users.count(), 2)

    def test_required_fields(self):
        organization_url = '/{}/organizations/{}/'.format(
            self.api_prefix, self.administrator.organization_id)
        invite_user_url = self.client.get(organization_url).json()[
            '_links']['invite_user']['href']
        data = {"identifier": ""}
        resp = self.client.post(invite_user_url, data)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.administrator.organization.users.count(), 2)

    def test_children_organization(self):
        child = OrganizationFactory(parent=self.administrator.organization)
        child_url = '/{}/organizations/{}/'.format(self.api_prefix, child.id)

        invite_user_url = self.client.get(child_url).json()[
            '_links']['invite_user']['href']

        data = {"identifier": faker.safe_email()}
        resp = self.client.post(invite_user_url, data)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["identifier"], data['identifier'])
        self.assertEqual(self.administrator.organization.users.count(), 2)
        self.assertEqual(child.users.count(), 1)
        self.assertFalse(MunchUser.objects.filter(
            identifier=data['identifier']).first().is_active)

    def test_not_owned_organization(self):
        another_org = OrganizationFactory()
        another_org_url = '/{}/organizations/{}/invite_user/'.format(
            self.api_prefix, another_org.id)

        data = {"identifier": faker.safe_email()}
        resp = self.client.post(another_org_url, data)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.administrator.organization.users.count(), 2)
        self.assertEqual(another_org.users.count(), 0)
