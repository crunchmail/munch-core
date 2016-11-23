import random
import logging
from unittest.mock import patch
from unittest.mock import MagicMock

import PIL.Image
from django.test import TestCase
from django.core.files.base import ContentFile
from django.core.files.temp import NamedTemporaryFile

from munch.apps.users.tests.factories import UserFactory

from .models import Image
from .models import UploadDuplicateError


logging.disable(logging.CRITICAL)


def mock_get_app_url(*args, **kwargs):
    def get_app_url():
        return 'http://uploads.example.com'

    m = MagicMock()
    m.side_effect = get_app_url()
    return m


class ImageTestCaseMixin:
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


@patch('munch.core.mail.utils.get_app_url', mock_get_app_url)
class ImageTestCase(TestCase, ImageTestCaseMixin):
    def setUp(self):
        self.admin = UserFactory(
            is_admin=True, is_active=True, is_superuser=True)
        self.admin.organization.can_attach_files = False
        self.admin.organization.can_external_optout = False
        self.admin.organization.save()
        self.organization = self.admin.organization

    def test_image_creation(self):
        image = Image(organization=self.organization)
        file = ContentFile(self.create_random_image().read())

        image.file.save('random_image.png', file, save=False)
        image.save()
        self.assertNotEqual('', image.hash)

        image_file = PIL.Image.open(image.file.file)
        self.assertEqual((600, 450), image_file.size)

    def test_image_duplicate(self):
        image = Image(organization=self.organization)
        file = ContentFile(self.create_random_image().read())

        image.file.save('random_image.png', file, save=False)
        image.save()

        image = Image(organization=self.organization)

        image.file.save('random_image2.png', file, save=False)
        with self.assertRaises(UploadDuplicateError):
            image.save()

    def test_upload_differentImage(self):
        image = Image(organization=self.organization)
        file = ContentFile(self.create_random_image(100, 100).read())

        image.file.save('random_image.png', file, save=False)
        image.save()

        image = Image(organization=self.organization)
        file = ContentFile(self.create_random_image(101, 101).read())

        image.file.save('random_image.png', file, save=False)
        try:
            image.save()
        except UploadDuplicateError:
            self.fail('Creating a new image should not raise an exception.')

    def test_image_resizing(self):
        image = Image(organization=self.organization)
        file = ContentFile(self.create_random_image(100, 100).read())

        image.file.save('random_image.png', file, save=False)
        image.save()

        image_file = PIL.Image.open(image.file.file)
        self.assertEqual((100, 100), image_file.size)

        image = Image(organization=self.organization)
        file = ContentFile(self.create_random_image(100, 100).read())

        image.file.save('random_image.png', file, save=False)
        image.width = 50
        image.save()

        image_file = PIL.Image.open(image.file.file)
        self.assertEqual((50, 50), image_file.size)

    def test_backend(self):
        pass  # will be implemented when new backends will be available

    def test_resize_in_edit_mode(self):
        image = Image(organization=self.organization)
        image.resize_image = MagicMock()
        file = ContentFile(self.create_random_image(100, 100).read())

        image.file.save('random_image.png', file, save=False)
        image.save()

        image.resize_image.assert_called_with()

        image.resize_image.reset_mock()

        image.expiration = '10:00'
        image.save()

        self.assertFalse(
            image.resize_image.called,
            'Saving an existing image should not call '
            'resize_image, except if width has changed')

        image.resize_image.reset_mock()

        image.width = 200
        image.save()

        self.assertTrue(
            image.resize_image.called,
            'Saving an existing image with a new width should '
            'call resize_image')
