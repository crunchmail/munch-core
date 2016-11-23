import os
import shutil
import logging

from django.test import Client
from django.test import TestCase
from django.conf import settings
from django.test.utils import override_settings

from .models import InlineImage
from .models import HostedImage
from .exceptions import TooBigMedia
from .exceptions import InvalidMimeType

from munch.apps.users.tests.factories import UserFactory
from munch.apps.campaigns.tests.factories import MessageFactory


logging.disable(logging.CRITICAL)


class TestHostedMedia(TestCase):
    """ Deletes the media dir once tests are completed

    WARNING: use that only if you are in tests, with an overloaded  MEDIA_ROOT
    Normally it's fine within munch, defined in munch/test_settings.py
    """
    def classSetUp(self):
        # mktemp will only be used for the 1st Case using this parent class
        if not os.path.exists(settings.MEDIA_ROOT):
            os.mkdir(settings.MEDIA_ROOT)

    def classTearDown(self):
        try:
            shutil.rmtree(settings.MEDIA_ROOT)
        except Exception:
            pass


class TestHostedImage(TestHostedMedia):
    def setUp(self):
        self.user = UserFactory()

    def test_image_toobig(self):
        class SmallHostedImage(HostedImage):
            # very small
            MAX_SIZE = 100
        img_url = 'http://www.oasiswork.fr/uploads/logo_oasiswork.jpg'

        with self.assertRaises(TooBigMedia):
            img = SmallHostedImage(
                img_url, organization=self.user.organization)
            img.store()

    def test_wrong_mimetype(self):
        html_document = 'data:image/gif;base64,PGh0bWw+PC9odG1sPg=='
        image = InlineImage(html_document, organization=self.user.organization)
        with self.assertRaises(InvalidMimeType):
            image.store()


class TestHostedImageClient(TestHostedMedia):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()

    def test_fetch_hosted_image_ok(self):
        img_url = 'http://www.oasiswork.fr/uploads/logo_oasiswork.jpg'
        img = HostedImage(img_url, organization=self.user.organization)
        stored_url = img.store()
        self.assertTrue(stored_url.startswith('http://munch.example.com'))

    def test_fetch_inline_image_ok(self):
        img_data = (
            "data:image/gif;base64,R0lGODlhDwAPAKECAAAAzMzM/////"
            "wAAACwAAAAADwAPAAACIISPeQHsrZ5ModrLlN48CXF8m2iQ3YmmKqVlRtW4ML"
            "wWACH+H09wdGltaXplZCBieSBVbGVhZCBTbWFydFNhdmVyIQAAOw==")
        img = InlineImage(img_data, organization=self.user.organization)
        stored_url = img.store()
        self.assertTrue(stored_url.startswith('http://munch.example.com'))


@override_settings(SECRET_KEY='123412341234')
class TestHostedMessage(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)

    def test_hosted_mail_without_key_works(self):
        response = self.client.get('/archive/{}/'.format(
            self.message.identifier))
        self.assertEqual(response.status_code, 200)

    def test_hosted_mail_bad_uuid(self):
        response = self.client.get('/archive/1584498-148484/')
        self.assertEqual(response.status_code, 404)
