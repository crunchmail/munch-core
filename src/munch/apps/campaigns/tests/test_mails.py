from unittest.mock import patch

from django.test import TestCase
from django.conf import settings
from django.core.files.base import ContentFile
from django.test.utils import override_settings
from django.core.mail import EmailMultiAlternatives
from django.core.files.storage import default_storage
from slimta.envelope import Envelope

from munch.core.utils.tests import temporary_settings
from munch.core.mail.models import return_path_parser
from munch.core.mail.models import unsubscribe_parser
from munch.apps.users.tests.factories import UserFactory
from munch.apps.spamcheck.tests import get_spam_result_mock
from munch.apps.optouts.tests.factories import OptOutFactory

from ..tasks import handle_dsn
from ..models import Mail
from ..models import Message
from ..models import MailStatus
from ..models import MessageAttachment

from .factories import MailFactory
from .factories import MessageFactory
from .factories import MailStatusFactory


class MailTest(TestCase):
    @override_settings(BYPASS_DNS_CHECKS=True)
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)

    def test_new_mail_creates_mailstatus(self):
        statuses = MailStatus.objects.filter(mail__message=self.message)
        self.assertEqual(statuses.count(), 0)
        mail = MailFactory(message=self.message)
        self.assertEqual(mail.statuses.count(), 1)
        self.assertEqual(mail.statuses.first().status, MailStatus.UNKNOWN)

    def test_new_bulk_mail_creates_mailstatus(self):
        statuses = MailStatus.objects.filter(mail__message=self.message)
        self.assertEqual(statuses.count(), 0)
        mail_attrs = MailFactory.attributes()
        mail_attrs.update({'message': self.message})
        Mail.objects.bulk_create([Mail(**mail_attrs)])
        m = Mail.objects.get(recipient=mail_attrs['recipient'])
        self.assertEqual(m.statuses.count(), 1)
        self.assertEqual(m.statuses.first().status, MailStatus.UNKNOWN)
        self.assertEqual(m.statuses.last().creation_date, m.latest_status_date)
        self.assertEqual(m.statuses.first().creation_date, m.first_status_date)

    def test_new_mailstatus_updates_mail(self):
        mail = MailFactory(message=self.message)
        mail_status = MailStatusFactory(mail=mail, status=MailStatus.QUEUED)
        statuses = MailStatus.objects.filter(mail__message=self.message)
        self.assertEqual(statuses.count(), 2)
        self.assertEqual(mail.statuses.last(), mail_status)
        self.assertEqual(mail.curstatus, MailStatus.QUEUED)

    def test_to_mail(self):
        mail = MailFactory(message=self.message)
        message = mail.as_message()
        self.assertIsInstance(message, EmailMultiAlternatives)

    def test_to_mail_includes_unsubscription_link(self):
        mail = MailFactory(message=self.message)
        self.assertIn('/optout/', mail.as_message().body)

    def test_to_mail_html_includes_view_in_browser(self):
        user = UserFactory()
        message = MessageFactory(
            author=user, html='WEB_VERSION_URL UNSUBSCRIBE_URL')
        mail = MailFactory(message=message)
        self.assertIn('/archive/', mail.as_message().body)

    def test_to_mail_html_does_not_include_view_in_browser(self):
        user = UserFactory()
        message = MessageFactory(author=user, html='test UNSUBSCRIBE_URL')
        mail = MailFactory(message=message)
        self.assertNotIn('/archive/', mail.as_message().body)

    def test_to_mail_includes_ok_topic(self):
        mail = MailFactory(message=self.message)
        message = mail.as_message()
        self.assertEqual(
            message.message().get('Subject'), self.message.subject)

    def test_addrs(self):
        mail = MailFactory(message=self.message)
        self.assertTrue(unsubscribe_parser.is_valid(mail.unsubscribe_addr))
        self.assertTrue(return_path_parser.is_valid(mail.envelope_from))


class MailMergeTests(TestCase):
    def test_mailmerge(self):
        user = UserFactory()
        message = MessageFactory(
            author=user, html='<h1>Hi {{ first_name }} %s</h1>' % (
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER']))
        mail = MailFactory(message=message, properties={'first_name': 'John'})

        with patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=get_spam_result_mock):
            message.save()

        content = message.to_mail(mail)
        self.assertNotIn('{{ first_name }}', content.alternatives[0][0])
        self.assertIn('John', content.alternatives[0][0])


@override_settings(OPTOUTS_ADDRESS='')
class MailSending(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)

        settings.CAMPAIGNS['SKIP_SPAM_CHECK'] = True

    def test_fire_message(self):
        MailFactory(message=self.message)

        a_mail = MailFactory(message=self.message)
        self.assertNotEqual(a_mail.identifier, '')

        self.message.status = 'sending'
        self.message.author.organization.settings.notify_message_status = False
        self.message.save()  # Fires the message

        self.assertEqual(self.message.mails.filter(
            curstatus=MailStatus.SENDING).count(), 2)
        self.assertEqual(self.message.mails.filter(
            curstatus=MailStatus.DELIVERED).count(), 0)
        for mail in self.message.mails.all():
            MailStatusFactory(mail=mail, status=MailStatus.DELIVERED)
        self.assertEqual(self.message.status, self.message.SENT)

    def test_fire_message_handles_optouted(self):
        """
        Checks that an ignored recipient for cause of previous optout on its
        address will  put the Mail in IGNORED state, and will not prevent the
        other mail to reach its SENDING state and the Message to complete.
        """
        mail = MailFactory(message=self.message)
        OptOutFactory(
            author=self.message.author, category=self.message.category,
            identifier=mail.identifier, address=mail.recipient)

        # A prev message with same recipient had an optout
        message = MessageFactory(author=self.user)
        mail_ok = MailFactory(message=message)
        mail_optouted = MailFactory(message=message, recipient=mail.recipient)

        message.status = 'sending'
        message.author.organization.settings.notify_message_status = False
        message.save()  # Fires the message

        self.assertEqual(message.mails.filter(
            curstatus=MailStatus.SENDING).count(), 1)
        self.assertEqual(message.mails.filter(
            curstatus=MailStatus.DELIVERED).count(), 0)
        self.assertEqual(Mail.objects.get(
            pk=mail_optouted.pk).curstatus, MailStatus.IGNORED)

        handle_dsn(
            'To: {}'.format(mail_ok.envelope_from),
            {
                'Final-Recipient': mail_ok.recipient,
                'Diagnostic-Code': 'Delivered',
                'Status': '2.0.0',
                'Arrival-Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'})

        self.assertEqual(
            Message.objects.get(pk=message.pk).status, message.SENT)

    def test_fire_message_good_headers(self):
        """ Some headers are required for mass mailing, check them """
        MailFactory(message=self.message)
        MailFactory(message=self.message)

        self.message.status = 'sending'
        self.message.author.organization.settings.notify_message_status = False
        self.message.save()

        # Fires the message
        self.assertEqual(self.message.mails.filter(
            curstatus=MailStatus.SENDING).count(), 2)
        self.assertEqual(self.message.mails.filter(
            curstatus=MailStatus.DELIVERED).count(), 0)
        for mail in self.message.mails.all():
            MailStatus.objects.create(mail=mail, status=MailStatus.DELIVERED)
        self.assertEqual(self.message.status, self.message.SENT)

        first_mail = self.message.mails.all().first()
        first_headers = dict(first_mail.as_message().message())
        self.assertIn('List-Unsubscribe', first_headers)
        self.assertEqual(first_headers['Precedence'], 'bulk')

        # checks that the url in the email headers for abuse is reachable
        abuse_msg = first_headers['X-Report-Abuse']
        abuse_url = abuse_msg.split(' ')[-1]
        response = self.client.get(abuse_url)
        self.assertEqual(response.status_code, 200)

    def test_fire_message_with_attachments(self):
        MailFactory(message=self.message)

        default_storage.save('foo.txt', ContentFile('testfoo'))

        ma = MessageAttachment(message=self.message, file='foo.txt')
        self.message.author.organization.settings.notify_message_status = False
        ma.save()

        # Fires the message
        self.message.status = 'sending'
        self.message.save()

        first_mail = self.message.mails.all().first()
        message = first_mail.message.to_mail(first_mail)
        self.assertEqual(len(message.attachments), 1)
        filename, content, mimetype = message.attachments[0]
        self.assertEqual(filename, 'foo.txt')
        self.assertEqual(content, 'testfoo')
        self.assertEqual(mimetype, 'text/plain')

        default_storage.delete('foo.txt')

    def test_fire_message_with_bin_attachments(self):
        MailFactory(message=self.message)

        default_storage.save(
            'foo.bmp',
            ContentFile(
                b'BM\x8e\x00\x00\x00\x00\x00\x00\x00\x8a\x00\x00\x00|\x00\x00'
                b'\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x10\x00\x03\x00'
                b'\x00\x00\x04\x00\x00\x00\x13\x0b\x00\x00\x13\x0b\x00\x00\x00'
                b'\x00\x00\x00\x00\x00\x00\x00\x00\xf8\x00\x00\xe0\x07\x00\x00'
                b'\x1f\x00\x00\x00\x00\x00\x00\x00BGRs\x00\x00\x00\x00\x00\x00'
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00'
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff'
                b'\x00\x00'))

        ma = MessageAttachment(message=self.message, file='foo.bmp')
        ma.save()

        # Fires the message
        self.message.status = 'sending'
        self.message.author.organization.settings.notify_message_status = False
        self.message.save()

        first_mail = self.message.mails.all().first()
        message = first_mail.message.to_mail(first_mail)
        self.assertEqual(len(message.attachments), 1)
        filename, content, mimetype = message.attachments[0]
        self.assertEqual(filename, 'foo.bmp')
        self.assertEqual(len(content), 142)
        # the mimetype depends on python versions.
        self.assertIn(mimetype, ('application/octet-stream', 'image/x-ms-bmp'))

        default_storage.delete('foo.bmp')
