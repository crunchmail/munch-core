from django.test import TestCase
from django.db import IntegrityError

from .factories import UserFactory
from .factories import APIApplicationFactory
from .factories import SmtpApplicationFactory


class APIApplicationTestCase(TestCase):
    def test_create_application(self):
        application = APIApplicationFactory()

        secret = application.secret

        self.assertTrue(application.secret)
        self.assertTrue(application.author)
        self.assertTrue(application.identifier)

        application.regen_secret()

        self.assertNotEqual(secret, application.secret)

        with self.assertRaises(IntegrityError):
            APIApplicationFactory(
                author=application.author, identifier=application.identifier)


class SmtpApplicationTestCase(TestCase):
    def test_create_application(self):
        application = SmtpApplicationFactory()

        username = application.username
        secret = application.secret

        self.assertTrue(application.secret)
        self.assertTrue(application.username)
        self.assertTrue(application.author)
        self.assertTrue(application.identifier)

        application.regen_credentials()
        application.save()

        self.assertNotEqual(secret, application.secret)
        self.assertNotEqual(username, application.username)

        with self.assertRaises(IntegrityError):
            SmtpApplicationFactory(username=application.username)

        with self.assertRaises(IntegrityError):
            SmtpApplicationFactory(
                author=application.author, identifier=application.identifier)
