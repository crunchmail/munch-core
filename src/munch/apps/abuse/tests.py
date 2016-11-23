import logging

from django.test import TestCase

from munch.apps.campaigns.models import OptOut
from munch.apps.users.tests.factories import UserFactory
from munch.apps.campaigns.tests.factories import MailFactory
from munch.apps.campaigns.tests.factories import MessageFactory
from munch.apps.campaigns.tests.factories import PreviewMailFactory

from .forms import AbuseNotificationForm


logging.disable(logging.CRITICAL)


class TestAbuseForms(TestCase):
    def test_mail_resolution(self):
        user = UserFactory()
        message = MessageFactory(author=user)
        mail = MailFactory(message=message)
        f = AbuseNotificationForm({
            'mail': mail.identifier,
            'comments': 'test'})
        f.is_valid()
        f.save()

    def test_form_validation(self):
        user = UserFactory()
        message = MessageFactory(author=user)
        mail = MailFactory(message=message)
        f = AbuseNotificationForm({
            'mail': mail.identifier,
            'comments': ''})
        self.assertFalse(f.is_valid())


class TestAbuseURL(TestCase):
    def test_abuse_url(self):
        user = UserFactory()
        message = MessageFactory(author=user)
        mail = MailFactory(message=message)
        self.assertEqual(
            mail.abuse_url,
            'http://test.munch.example.com/abuse/report/{}/'.format(
                mail.identifier))


class TestAbuseReport(TestCase):
    def test_abuse_makes_optout(self):
        """ An abuse should create an optout for the given mail """
        user = UserFactory()
        message = MessageFactory(author=user)
        mail = MailFactory(message=message)
        response = self.client.post(
            'http://test.munch.example.com/abuse/report/{}/'.format(
                mail.identifier),
            {'mail': mail.identifier, 'comments': 'test'})
        self.assertEqual(response.status_code, 302)
        optout = OptOut.objects.get(identifier=mail.identifier)
        self.assertEqual(optout.origin, OptOut.BY_ABUSE)


class TestAbusePreview(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)

    def test_abuse_page_not_preview(self):
        """ Report page displays no warning"""
        mail = MailFactory(message=self.message)
        response = self.client.get('/abuse/report/{}/'.format(mail.identifier))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "from a preview message", response.content.decode())

    def test_abuse_page_preview(self):
        """ Report page displays a warning"""
        preview = PreviewMailFactory(message=self.message)
        response = self.client.get(
            '/abuse/report/{}/'.format(preview.identifier))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "from a preview message", response.content.decode())
