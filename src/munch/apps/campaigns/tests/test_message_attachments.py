import shutil

from django.test import TestCase
from django.test.utils import override_settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from munch.apps.users.tests.factories import UserFactory
from munch.apps.campaigns.models import MessageAttachment
from munch.apps.campaigns.tests.factories import MessageFactory


class MessageAttachmentTest(TestCase):
    @override_settings(BYPASS_DNS_CHECKS=True)
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)

    def tearDown(self):
        shutil.rmtree(default_storage.location)

    def test_delete_message_with_shared_attachment(self):
        default_storage.save('foo.txt', ContentFile('testfoo'))

        message_attachment = MessageAttachment.objects.create(
            message=self.message, file='foo.txt')

        another_message = MessageFactory(author=self.user)

        another_message_attachment = MessageAttachment.objects.create(
            message=another_message, file='foo.txt')

        self.assertTrue(default_storage.exists(message_attachment.file.path))
        self.assertTrue(default_storage.exists(
            another_message_attachment.file.path))

        self.message.delete()

        self.assertTrue(default_storage.exists(message_attachment.file.path))
        self.assertTrue(default_storage.exists(
            another_message_attachment.file.path))

        another_message.delete()

        self.assertFalse(default_storage.exists(message_attachment.file.path))
        self.assertFalse(default_storage.exists(
            another_message_attachment.file.path))
