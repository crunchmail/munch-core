import random
from unittest.mock import patch

import PIL.Image
from django.test import TestCase
from django.core.files.temp import NamedTemporaryFile
from rest_framework.test import APIClient

from munch.apps.users.tests.factories import UserFactory
from munch.core.utils.tests import HttpBasicTestCaseMixin

from ...models import Image
from ...tests import ImageTestCaseMixin
from ...tests import mock_get_app_url


class ImageAPITestCase(TestCase, ImageTestCaseMixin):
    def setUp(self):
        self.api_prefix = 'v1'
        self.admin = UserFactory(
            is_admin=True, is_active=True, is_superuser=True)
        self.admin.organization.can_attach_files = False
        self.admin.organization.can_external_optout = False
        self.admin.organization.save()

        self.client = APIClient()
        self.client.login(
            identifier=self.admin.identifier, password='password')
        self.organization = self.admin.organization

    def test_api_listing(self):
        response = self.client.get('/{}/upload-store/images/'.format(
            self.api_prefix))
        self.assertEqual(405, response.status_code)

    def test_api_creation(self):
        file = self.create_random_image()

        response = self.client.post(
            '/{}/upload-store/images/'.format(self.api_prefix),
            {'file': file}, format='multipart')
        self.assertEqual(201, response.status_code)
        obj = Image.objects.last()
        self.assertRegexpMatches(
            response.data['file'], '{}\.png$'.format(obj.hash))

    def test_api_dup_creation(self):
        file = self.create_random_image()

        response = self.client.post(
            '/{}/upload-store/images/'.format(self.api_prefix),
            {'file': file}, format='multipart')
        self.assertEqual(201, response.status_code)

        file.file.seek(0)
        response = self.client.post(
            '/{}/upload-store/images/'.format(self.api_prefix),
            {'file': file}, format='multipart')
        self.assertEqual(201, response.status_code)

        file.file.seek(0)
        response = self.client.post(
            '/{}/upload-store/images/'.format(self.api_prefix),
            {'file': file, 'expiration': '10:00'}, format='multipart')
        self.assertEqual(201, response.status_code)

    def test_api_creation_with_width(self):
        file = self.create_random_image()

        response = self.client.post(
            '/{}/upload-store/images/'.format(self.api_prefix),
            {'file': file, 'width': 100, 'expiration': '10:00'},
            format='multipart')
        self.assertEqual(201, response.status_code)
        self.assertEqual(100, response.data['width'])
        self.assertEqual('00:10:00', response.data['expiration'])

        obj = Image.objects.last()
        image_file = PIL.Image.open(obj.file.file)
        self.assertEqual((100, 75), image_file.size)

    def test_api_creation_with_too_large_width(self):
        actual_file_width = 2
        asked_file_width = 10
        file = self.create_random_image(width=actual_file_width, height=2)

        response = self.client.post(
            '/{}/upload-store/images/'.format(self.api_prefix),
            {'file': file, 'width': asked_file_width, 'expiration': '10:00'},
            format='multipart')
        self.assertEqual(201, response.status_code)
        self.assertEqual(actual_file_width, response.data['width'])

    def test_api_retrieve(self):
        file = self.create_random_image()

        response = self.client.post(
            '/{}/upload-store/images/'.format(self.api_prefix),
            {'file': file}, format='multipart')
        response = self.client.get(response.data['url'])
        self.assertEqual(200, response.status_code, 'Image retrieving failed')


@patch('munch.core.mail.utils.get_app_url', mock_get_app_url)
class PermissionsAPITestCase(TestCase, HttpBasicTestCaseMixin):
    def setUp(self):
        self.api_prefix = 'v1'
        self.admin = UserFactory(
            is_admin=True, is_active=True, is_superuser=True)
        self.admin.organization.can_attach_files = False
        self.admin.organization.can_external_optout = False
        self.admin.organization.save()

    def create_random_image(self, width=800, height=600):
        color = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255))
        image = PIL.Image.new('RGB', (width, height), color)
        temp = NamedTemporaryFile(suffix='.png')
        image.save(temp, 'png')
        temp.seek(0)
        return temp

    def test_api_creation_permission(self):
        file = self.create_random_image()

        response = self.client.post(
            '/{}/upload-store/images/'.format(self.api_prefix),
            {'file': file}, format='multipart')
        self.assertEqual(401, response.status_code)

    def test_api_creation_permission_with_secret(self):
        file = self.create_random_image()
        auth_headers = self.http_basic_headers(
            'api', self.admin.secret)

        response = self.client.post(
            '/{}/upload-store/images/'.format(self.api_prefix), {'file': file},
            format='multipart', **auth_headers)
        self.assertEqual(201, response.status_code)

    def test_api_retrieve_permission(self):
        file = self.create_random_image()
        self.client.login(
            identifier=self.admin.identifier, password='password')
        response = self.client.post(
            '/{}/upload-store/images/'.format(self.api_prefix),
            {'file': file}, format='multipart')
        self.client.logout()
        response = self.client.get(response.data['url'])
        self.assertEqual(
            200, response.status_code,
            'Image retrieving failed while logged out')
