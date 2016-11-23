from django.test import TestCase

from munch.apps.campaigns.models import OptOut
from munch.apps.campaigns.tests.factories import MailFactory
from munch.apps.campaigns.tests.factories import MessageFactory
from munch.apps.campaigns.tests.factories import PreviewMailFactory
from munch.apps.users.tests.factories import UserFactory

from .factories import OptOutFactory


class TestOptOut(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)

    def test_new_optout(self):
        """ OptOut when no other opptout exist for this email"""
        mail = MailFactory(message=self.message)

        self.assertFalse(OptOut.objects.filter(
            identifier=mail.identifier).exists())
        response = self.client.post(
            '/h/subscriptions/{}/optout/'.format(mail.identifier))
        self.assertEqual(response.status_code, 302)

        o = OptOut.objects.get(identifier=mail.identifier)
        self.assertEqual(o.origin, OptOut.BY_WEB)

    def test_optout_again(self):
        """ OptOut when a previous optout exists:

        Keep it but change date and origin"""
        mail = MailFactory(message=self.message)
        first_optout = OptOutFactory(
            identifier=mail.identifier,
            address=mail.recipient,
            origin=OptOut.BY_MAIL)
        first_optout_date = first_optout.creation_date

        response = self.client.post(
            '/h/subscriptions/{}/optout/'.format(mail.identifier))
        self.assertEqual(response.status_code, 302)

        o = OptOut.objects.get(identifier=mail.identifier)
        self.assertEqual(o, first_optout)
        self.assertEqual(o.origin, OptOut.BY_WEB)
        self.assertNotEqual(o.creation_date, first_optout_date)

    def test_new_optout_external_post(self):
        self.message.external_optout = True
        self.message.save()
        mail = MailFactory(message=self.message)

        self.assertFalse(OptOut.objects.filter(
            identifier=mail.identifier).exists())
        response = self.client.post(
            '/h/subscriptions/{}/optout/'.format(mail.identifier))
        self.assertEqual(response.status_code, 405)

        self.assertFalse(OptOut.objects.filter(
            identifier=mail.identifier).exists())

    def test_new_optout_external_get(self):
        self.message.external_optout = True
        self.message.save()
        mail = MailFactory(message=self.message)

        self.assertFalse(OptOut.objects.filter(
            identifier=mail.identifier).exists())
        response = self.client.get(
            '/h/subscriptions/{}/optout/'.format(mail.identifier))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'should get in touch with him', response.content.decode())

    def test_optout_page_not_preview(self):
        """ Unsubscribe page displays no warning"""
        mail = MailFactory(message=self.message)
        response = self.client.get(
            '/h/subscriptions/{}/optout/'.format(mail.identifier))
        self.assertEqual(response.status_code, 200)

        self.assertNotIn(
            "from a preview message", response.content.decode())

    def test_optout_page_preview(self):
        """ Unsubscribe page displays a warning"""

        pm = PreviewMailFactory(message=self.message)
        response = self.client.get(
            '/h/subscriptions/{}/optout/'.format(pm.identifier))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "from a preview message", response.content.decode())
