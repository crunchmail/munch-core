from django.test import TestCase
from django.test.utils import override_settings
from django.core.exceptions import ValidationError

from .factories import MailFactory
from .factories import MessageFactory
from munch.apps.users.tests.factories import UserFactory


class MailValidatorTest(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_ok(self):
        message = MessageFactory(author=self.user)
        with override_settings(BYPASS_DNS_CHECKS=False):
            mail = MailFactory(message=message)
            mail.full_clean()

    def test_not_an_email(self):
        message = MessageFactory(author=self.user)
        with self.assertRaisesRegexp(ValidationError, 'a valid email address'):
            with override_settings(BYPASS_DNS_CHECKS=False):
                mail = MailFactory(
                    recipient='eitsuanetisanetsunaetsurn', message=message)
                mail.full_clean()

    def test_not_an_email_bis(self):
        message = MessageFactory(author=self.user)
        with self.assertRaisesRegexp(ValidationError, 'a valid email address'):
            with override_settings(BYPASS_DNS_CHECKS=False):
                mail = MailFactory(message=message, recipient='foo@bar')
                mail.full_clean()

    def test_not_a_valid_domain(self):
        message = MessageFactory(author=self.user)
        # example.com has no MX record
        with self.assertRaisesRegexp(ValidationError, '^((?!invalide).)*$'):
            with override_settings(BYPASS_DNS_CHECKS=False):
                message.sender_email = 'foo@example.com'
                message.save()

        mail = MailFactory(
            message=message, recipient='test@example.com')
        mail.full_clean()
        message.save()
