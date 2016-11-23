from django.test import TestCase
from django.core import mail as django_mail
from django.test.utils import override_settings

from munch.apps.users.tests.factories import UserFactory
from munch.apps.optouts.tests.factories import OptOutFactory

from ..models import OptOut
from .factories import MailFactory
from .factories import MessageFactory


@override_settings(SKIP_SPAM_CHECK=True)
class NotificationTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.user.organization.contact_email = 'foo@bar'
        self.user.organization.settings.save()
        self.message = MessageFactory(author=self.user)
        django_mail.outbox = []

    def test_notify_optout_by_bounce(self):
        mail = MailFactory(message=self.message)
        mail.message.author.organization.settings.notify_optouts = True
        mail.message.author.organization.settings.save()
        OptOutFactory(
            identifier=mail.identifier,
            address=mail.recipient,
            origin=OptOut.BY_BOUNCE)

        self.assertEqual(len(django_mail.outbox), 0)

    def test_notify_optout(self):
        mail = MailFactory(message=self.message)
        mail.message.author.organization.settings.notify_optouts = True
        mail.message.author.organization.settings.save()
        OptOutFactory(
            author=mail.message.author,
            category=mail.message.category,
            identifier=mail.identifier,
            address=mail.recipient,
            origin=OptOut.BY_WEB)

        first_mail = django_mail.outbox[0]

        self.assertIn('no-reply', first_mail.from_email)

    def test_notify_sending(self):
        MailFactory(message=self.message)
        self.message.status = 'sending'
        self.message.save()  # Fires the message

        first_mail = django_mail.outbox[0]

        self.assertIn(
            self.user.organization.contact_email, first_mail.to)

    def test_notify_sending_good_count(self):
        MailFactory(message=self.message)
        MailFactory(message=self.message)

        self.message.status = 'sending'
        self.message.save()  # Fires the message

        first_mail = django_mail.outbox[0]

        self.assertIn('2 recipient(s) will receive', first_mail.body)
        self.assertIn("no recipients have been ignored", first_mail.body)

    def test_notify_sent(self):
        MailFactory(message=self.message)
        MailFactory(message=self.message)

        self.message.status = self.message.SENDING
        self.message.save()
        django_mail.outbox = []

        self.message.status = self.message.SENT
        self.message.save()
        first_mail = django_mail.outbox[0]
        self.assertIn(
            self.user.organization.contact_email, first_mail.to)
        self.assertIn('Total emails: 2', first_mail.body)
