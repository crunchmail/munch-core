from django.test import TestCase
from django.conf import settings
from rest_framework.test import APIClient

from munch.apps.users.tests.factories import UserFactory
from munch.apps.campaigns.tests.factories import MessageFactory

from ...models import Category
from ...tests.factories import CategoryFactory

class CategoryAPITestCase(TestCase):
    def setUp(self):
        self.api_prefix = 'v1'
        self.user = UserFactory(groups=['administrators'])

        self.client = APIClient()
        self.client.login(identifier=self.user.identifier, password='password')

        self.html = '<html>{}</html>'.format(
            settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])

    def test_can_delete_empty_category(self):
        category = CategoryFactory(author=self.user)
        self.assertEqual(Category.objects.count(), 1)
        resp = self.client.delete('/{}/categories/{}/'.format(
            self.api_prefix, category.pk))
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(Category.objects.count(), 0)

    def test_cannot_delete_non_empty_category(self):
        category = CategoryFactory(author=self.user)

        MessageFactory(category=category, author=self.user)

        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Category.objects.first().messages.count(), 1)
        resp = self.client.delete('/{}/categories/{}/'.format(
            self.api_prefix, category.pk))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Category.objects.first().messages.count(), 1)

    def test_cannot_delete_not_owned_category(self):
        user = UserFactory(groups=['administrators'])

        category = CategoryFactory(author=user)

        self.assertEqual(Category.objects.count(), 1)
        resp = self.client.delete('/{}/categories/{}/'.format(
            self.api_prefix, category.pk))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Category.objects.count(), 1)
