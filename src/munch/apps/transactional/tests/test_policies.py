from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from slimta.envelope import Envelope
from slimta.relay import PermanentRelayError
from slimta.queue import QueueError
from faker import Factory as FakerFactory

from munch.core.models import Category
# from munch.core.utils.tests import temporary_settings
# from munch.core.tests.factories import CategoryFactory
from munch.apps.users.tests.factories import UserFactory
from munch.apps.users.tests.factories import SmtpApplicationFactory
from munch.apps.domains.tests.factories import SendingDomainFactory
from munch.apps.optouts.models import OptOut
from munch.apps.optouts.tests.factories import OptOutFactory

from ..models import Mail
from ..models import MailBatch
from ..policies.relay import headers as headers_policy
from ..policies.queue import bounces
from ..policies.queue import identifier
from ..policies.queue import store_mail
from ..policies.queue import sending_domain

faker = FakerFactory.create()


class PolicyCase(TestCase):
    def mk_envelope(self, data, sender=None, recipients=None):
        env = Envelope(sender=sender)
        env.parse(data)
        if not recipients:
            recipients = ['root@localhost']
        env.recipients = recipients
        return env


class TestStoreHeaders(PolicyCase):
    def setUp(self):
        self.smtp_application = SmtpApplicationFactory()
        self.domain = SendingDomainFactory(
            name='example.com',
            organization=self.smtp_application.author.organization)
        self.user = UserFactory(
            identifier='foo@example.com', last_login=timezone.now())

    def test_store_mail_empty(self):
        env = self.mk_envelope(b'')
        env.client = {'auth': (self.smtp_application.username, None)}
        env.user = self.user

        with self.assertRaises(PermanentRelayError):
            store_mail.Store().apply(env)

    def test_store_mail_minimal(self):
        env = self.mk_envelope(
            b"From: test-from@example.com\nSubject: foo\nTo: foo@bar",
            sender="test@example.com", recipients=['test-to@example.com'])
        env.client = {'auth': (self.smtp_application.username, None)}
        env.user = self.user

        identifier.Add().apply(env)
        bounces.Check().apply(env)
        sending_domain.Check().apply(env)
        store_mail.Store().apply(env)
        mail = Mail.objects.get(
            identifier=env.headers.get(settings.TRANSACTIONAL[
                'X_MESSAGE_ID_HEADER']))
        self.assertEqual(
            mail.headers, {
                'Subject': 'foo',
                'To': 'foo@bar',
                'From': "test-from@example.com",
                settings.TRANSACTIONAL[
                    'X_MESSAGE_ID_HEADER']: env.headers.get(
                        settings.TRANSACTIONAL['X_MESSAGE_ID_HEADER']),
                settings.TRANSACTIONAL[
                    'X_USER_ID_HEADER']: str(self.user.pk)})
        self.assertEqual(mail.sender, 'test@example.com')
        self.assertEqual(MailBatch.objects.count(), 0)
        self.assertEqual(Category.objects.count(), 0)

    def test_store_mail_with_batch(self):
        headers = (
            "From: test-from@example.com\n"
            "Subject: foo\nTo: foo@bar\n{}: foo").format(
                settings.TRANSACTIONAL['X_MAIL_BATCH_HEADER'])
        env = self.mk_envelope(
            headers.encode('utf-8'),
            sender="test@example.com", recipients=['test-to@example.com'])
        env.client = {'auth': (self.smtp_application.username, None)}
        env.user = self.user

        identifier.Add().apply(env)
        bounces.Check().apply(env)
        sending_domain.Check().apply(env)
        store_mail.Store().apply(env)
        mail = Mail.objects.get(
            identifier=env.headers.get(settings.TRANSACTIONAL[
                'X_MESSAGE_ID_HEADER']))

        self.assertEqual(mail.batch.name, 'foo')

        headers = (
            "From: test-from@example.com\n"
            "Subject: foo\nTo: foo@bar\n{}: foo").format(
                settings.TRANSACTIONAL['X_MAIL_BATCH_HEADER'])
        env = self.mk_envelope(
            headers.encode('utf-8'),
            sender="test@example.com", recipients=['test-to@example.com'])
        env.client = {'auth': (self.smtp_application.username, None)}
        env.user = self.user

        identifier.Add().apply(env)
        bounces.Check().apply(env)
        sending_domain.Check().apply(env)
        store_mail.Store().apply(env)

        self.assertEqual(MailBatch.objects.count(), 1)
        self.assertEqual(Category.objects.count(), 0)

    def test_store_mail_another_with_category(self):
        headers = (
            "From: test-from@example.com\n"
            "Subject: foo\nTo: foo@bar\n{}: foo").format(
                settings.TRANSACTIONAL['X_MAIL_BATCH_HEADER'])
        env = self.mk_envelope(
            headers.encode('utf-8'),
            sender="test@example.com", recipients=['test-to@example.com'])
        env.client = {'auth': (self.smtp_application.username, None)}
        env.user = self.user

        identifier.Add().apply(env)
        bounces.Check().apply(env)
        sending_domain.Check().apply(env)
        store_mail.Store().apply(env)
        mail = Mail.objects.get(
            identifier=env.headers.get(settings.TRANSACTIONAL[
                'X_MESSAGE_ID_HEADER']))

        self.assertEqual(mail.batch.name, 'foo')

        headers = (
            "From: test-from@example.com\n"
            "Subject: foo\nTo: foo@bar\n{}: foo\n{}: foo-cat").format(
                settings.TRANSACTIONAL['X_MAIL_BATCH_HEADER'],
                settings.TRANSACTIONAL['X_MAIL_BATCH_CATEGORY_HEADER'])
        env = self.mk_envelope(
            headers.encode('utf-8'),
            sender="test@example.com", recipients=['test-to@example.com'])
        env.client = {'auth': (self.smtp_application.username, None)}
        env.user = self.user

        identifier.Add().apply(env)
        bounces.Check().apply(env)
        sending_domain.Check().apply(env)
        store_mail.Store().apply(env)

        self.assertEqual(MailBatch.objects.count(), 1)
        self.assertEqual(Category.objects.count(), 1)

    def test_store_mail_category_scope(self):
        # Create first mail, batch and category
        headers = (
            "From: test-from@example.com\n"
            "Subject: foo\nTo: foo@bar\n{}: foo\n{}: foo-cat").format(
                settings.TRANSACTIONAL['X_MAIL_BATCH_HEADER'],
                settings.TRANSACTIONAL['X_MAIL_BATCH_CATEGORY_HEADER'])
        env = self.mk_envelope(
            headers.encode('utf-8'),
            sender="test@example.com", recipients=['test-to@example.com'])
        env.client = {'auth': (self.smtp_application.username, None)}
        env.user = self.user

        identifier.Add().apply(env)
        bounces.Check().apply(env)
        sending_domain.Check().apply(env)
        store_mail.Store().apply(env)
        # mail = Mail.objects.get(
        #     identifier=env.headers.get(settings.TRANSACTIONAL[
        #         'X_MESSAGE_ID_HEADER']))

        # Same batch name and category with another user
        another_smtp_application = SmtpApplicationFactory()
        SendingDomainFactory(
            name='example.com',
            organization=another_smtp_application.author.organization)

        headers = (
            "From: test-from@example.com\n"
            "Subject: foo\nTo: foo@bar\n{}: foo\n{}: foo-cat").format(
                settings.TRANSACTIONAL['X_MAIL_BATCH_HEADER'],
                settings.TRANSACTIONAL['X_MAIL_BATCH_CATEGORY_HEADER'])
        env = self.mk_envelope(
            headers.encode('utf-8'),
            sender="test@example.com", recipients=['test-to@example.com'])
        env.client = {'auth': (another_smtp_application.username, None)}
        env.user = self.user

        identifier.Add().apply(env)
        bounces.Check().apply(env)
        sending_domain.Check().apply(env)
        store_mail.Store().apply(env)
        # Mail.objects.get(
        #     identifier=env.headers.get(settings.TRANSACTIONAL[
        #         'X_MESSAGE_ID_HEADER']))

        self.assertEqual(Mail.objects.filter(
            author=self.smtp_application.author).count(), 1)
        self.assertEqual(Mail.objects.filter(
            author=another_smtp_application.author).count(), 1)
        self.assertEqual(Mail.objects.count(), 2)

        self.assertEqual(MailBatch.objects.filter(
            author=self.smtp_application.author).count(), 1)
        self.assertEqual(MailBatch.objects.filter(
            author=another_smtp_application.author).count(), 1)
        self.assertEqual(MailBatch.objects.count(), 2)

        self.assertEqual(Category.objects.filter(
            author=self.smtp_application.author).count(), 1)
        self.assertEqual(Category.objects.filter(
            author=another_smtp_application.author).count(), 1)
        self.assertEqual(Category.objects.count(), 2)

    def test_track_open_no_html(self):
        headers = (
            "From: test-from@example.com\n"
            "Subject: foo\nTo: foo@bar\n{}: true").format(
                settings.TRANSACTIONAL['X_MAIL_TRACK_OPEN_HEADER'])
        env = self.mk_envelope(
            headers.encode('utf-8') + '\n\nMy Message'.encode('utf-8'),
            sender="test@example.com", recipients=['test-to@example.com'])
        env.client = {'auth': (self.smtp_application.username, None)}
        env.user = self.user

        identifier.Add().apply(env)
        bounces.Check().apply(env)
        sending_domain.Check().apply(env)
        store_mail.Store().apply(env)
        headers, body = env.flatten()
        self.assertNotIn(
            'alt="" height="1" width="1" border="0" />', body.decode('utf-8'))
        self.assertNotIn(
            '/t/open/{}'.format(env.headers.get(settings.TRANSACTIONAL[
                'X_MESSAGE_ID_HEADER'])), body.decode('utf-8'))

    def test_track_open(self):
        headers = (
            'From: test-from@example.com\n'
            'Content-Type: multipart/alternative;\n'
            ' boundary="===============0445577956452755870=="\n'
            'Subject: foo\n'
            'To: foo@bar\n'
            '{}: true').format(
                settings.TRANSACTIONAL['X_MAIL_TRACK_OPEN_HEADER'])
        body = (
            '--===============0445577956452755870==\n'
            'Content-Type: text/plain; charset="us-ascii"\n'
            'MIME-Version: 1.0\n'
            'Content-Transfer-Encoding: 7bit\n'
            '\n'
            'My template in text to [1]\n'
            '\n'
            '[1]: http://google.it\n'
            '--===============0445577956452755870==\n'
            'Content-Type: text/html; charset="us-ascii"\n'
            'MIME-Version: 1.0\n'
            'Content-Transfer-Encoding: 7bit\n'
            '\n'
            '<a href="http://google.fr">Google!</a>\n'
            '<a href="http://google.com">Google COM</a>\n'
            '<strong>Strong jambon is strong</strong>\n'
            '--===============0445577956452755870==--\n')
        env = self.mk_envelope(
            headers.encode('utf-8') + body.encode('utf-8'),
            sender="test@example.com", recipients=['test-to@example.com'])
        env.client = {'auth': (self.smtp_application.username, None)}
        env.user = self.user

        identifier.Add().apply(env)
        bounces.Check().apply(env)
        sending_domain.Check().apply(env)
        store_mail.Store().apply(env)
        headers, body = env.flatten()
        self.assertIn(
            'alt="" height="1" width="1" border="0"', body.decode('utf-8'))
        self.assertIn(
            '/t/open/{}'.format(env.headers.get(settings.TRANSACTIONAL[
                'X_MESSAGE_ID_HEADER'])), body.decode('utf-8'))

    def test_track_clicks(self):
        headers = (
            'From: test-from@example.com\n'
            'Content-Type: multipart/alternative;\n'
            ' boundary="===============0445577956452755870=="\n'
            'Subject: foo\n'
            'To: foo@bar\n'
            '{}: true').format(
                settings.TRANSACTIONAL['X_MAIL_TRACK_CLICKS_HEADER'])
        body = (
            '--===============0445577956452755870==\n'
            'Content-Type: text/plain; charset="us-ascii"\n'
            'MIME-Version: 1.0\n'
            'Content-Transfer-Encoding: 7bit\n'
            '\n'
            'My template in text to [1]\n'
            '\n'
            '[1]: http://google.it\n'
            '--===============0445577956452755870==\n'
            'Content-Type: text/html; charset="us-ascii"\n'
            'MIME-Version: 1.0\n'
            'Content-Transfer-Encoding: 7bit\n'
            '\n'
            '<a href="http://google.fr">Google!</a>\n'
            '<a href="http://google.com">Google COM</a>\n'
            '<strong>Strong jambon is strong</strong>\n'
            '--===============0445577956452755870==--\n')
        env = self.mk_envelope(
            headers.encode('utf-8') + body.encode('utf-8'),
            sender="test@example.com", recipients=['test-to@example.com'])
        env.client = {'auth': (self.smtp_application.username, None)}
        env.user = self.user

        identifier.Add().apply(env)
        bounces.Check().apply(env)
        sending_domain.Check().apply(env)
        store_mail.Store().apply(env)
        headers, body = env.flatten()
        self.assertIn('/t/clicks/m/', body.decode('utf-8'))
        self.assertIn('http://google.it', body.decode('utf-8'))
        self.assertNotIn('http://google.fr', body.decode('utf-8'))
        self.assertNotIn('http://google.com', body.decode('utf-8'))

    def test_unsubscribe_link_no_placeholder(self):
        headers = (
            'From: test-from@example.com\n'
            'Content-Type: multipart/alternative;\n'
            ' boundary="===============0445577956452755870=="\n'
            'Subject: foo\n'
            'To: foo@bar\n'
            '{}: true').format(
                settings.TRANSACTIONAL['X_MAIL_UNSUBSCRIBE_HEADER'])
        body = (
            '--===============0445577956452755870==\n'
            'Content-Type: text/plain; charset="us-ascii"\n'
            'MIME-Version: 1.0\n'
            'Content-Transfer-Encoding: 7bit\n'
            '\n'
            'My template in text to [1]\n'
            '\n'
            '[1]: http://google.it\n'
            '--===============0445577956452755870==\n'
            'Content-Type: text/html; charset="us-ascii"\n'
            'MIME-Version: 1.0\n'
            'Content-Transfer-Encoding: 7bit\n'
            '\n'
            '<a href="http://google.fr">Google!</a>\n'
            '<a href="http://google.com">Google COM</a>\n'
            '<strong>Strong jambon is strong</strong>\n'
            '--===============0445577956452755870==--\n')
        env = self.mk_envelope(
            headers.encode('utf-8') + body.encode('utf-8'),
            sender="test@example.com", recipients=['test-to@example.com'])
        env.client = {'auth': (self.smtp_application.username, None)}
        env.user = self.user

        identifier.Add().apply(env)
        bounces.Check().apply(env)
        sending_domain.Check().apply(env)
        store_mail.Store().apply(env)
        headers, body = env.flatten()
        self.assertNotIn('/h/subscriptions/', body.decode('utf-8'))

    def test_unsubscribe_link(self):
        headers = (
            'From: test-from@example.com\n'
            'Content-Type: multipart/alternative;\n'
            ' boundary="===============0445577956452755870=="\n'
            'Subject: foo\n'
            'To: foo@bar\n'
            '{}: true').format(
                settings.TRANSACTIONAL['X_MAIL_UNSUBSCRIBE_HEADER'])
        body = (
            '--===============0445577956452755870==\n'
            'Content-Type: text/plain; charset="us-ascii"\n'
            'MIME-Version: 1.0\n'
            'Content-Transfer-Encoding: 7bit\n'
            '\n'
            'My template in text to [1]\n'
            'Unsub here: {}'
            '\n'
            '[1]: http://google.it\n'
            '--===============0445577956452755870==\n'
            'Content-Type: text/html; charset="us-ascii"\n'
            'MIME-Version: 1.0\n'
            'Content-Transfer-Encoding: 7bit\n'
            '\n'
            '<a href="http://google.fr">Google!</a>\n'
            '<a href="http://google.com">Google COM</a>\n'
            '<strong>Strong jambon is strong</strong>\n'
            '<a href="{}">Unsubscribe here</a>\n'
            '--===============0445577956452755870==--\n').format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'],
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        env = self.mk_envelope(
            headers.encode('utf-8') + body.encode('utf-8'),
            sender="test@example.com", recipients=['test-to@example.com'])
        env.client = {'auth': (self.smtp_application.username, None)}
        env.user = self.user

        identifier.Add().apply(env)
        bounces.Check().apply(env)
        sending_domain.Check().apply(env)
        store_mail.Store().apply(env)
        headers, body = env.flatten()
        self.assertIn('/h/subscriptions/', body.decode('utf-8'))


class TestBounces(PolicyCase):
    def setUp(self):
        self.smtp_application = SmtpApplicationFactory()
        self.domain = SendingDomainFactory(
            name='example.com',
            organization=self.smtp_application.author.organization)
        self.user = UserFactory(
            identifier='foo@example.com', last_login=timezone.now())

    def test_clean_address(self):
        optout = OptOutFactory(origin=OptOut.BY_WEB)
        envelope = self.mk_envelope(b'', recipients=[optout.address])
        envelope.client = {'auth': (self.smtp_application.username, None)}
        envelope.user = self.user
        identifier.Add().apply(envelope)
        bounces.Check().apply(envelope)

    def test_bounce(self):
        optout = OptOutFactory(origin=OptOut.BY_BOUNCE)
        envelope = self.mk_envelope(b'', recipients=[optout.address])
        envelope.client = {'auth': (self.smtp_application.username, None)}
        envelope.user = self.user
        identifier.Add().apply(envelope)
        with self.assertRaises(QueueError):
            bounces.Check().apply(envelope)

    def test_optout_batch_no_category(self):
        headers = (
            'From: test-from@example.com\n'
            'Subject: foo\n'
            'To: foo@bar\n'
            '{}: test').format(
                settings.TRANSACTIONAL['X_MAIL_BATCH_HEADER'])
        recipient = faker.email()
        envelope = self.mk_envelope(
            headers.encode('utf-8'),
            sender=faker.email(), recipients=[recipient])
        envelope.client = {'auth': (self.smtp_application.username, None)}
        envelope.user = self.user
        identifier.Add().apply(envelope)
        bounces.Check().apply(envelope)
        sending_domain.Check().apply(envelope)
        store_mail.Store().apply(envelope)

        self.client.post(
            '/h/subscriptions/{}/optout/'.format(
                envelope.headers.get(
                    settings.TRANSACTIONAL['X_MESSAGE_ID_HEADER'])))

        with self.assertRaises(QueueError):
            identifier.Add().apply(envelope)
            bounces.Check().apply(envelope)

    def test_optout_batch_no_category_another_user(self):
        headers = (
            'From: test-from@example.com\n'
            'Subject: foo\n'
            'To: foo@bar\n'
            '{}: test').format(
                settings.TRANSACTIONAL['X_MAIL_BATCH_HEADER'])
        recipient = faker.email()
        envelope = self.mk_envelope(
            headers.encode('utf-8'),
            sender=faker.email(), recipients=[recipient])
        envelope.client = {'auth': (self.smtp_application.username, None)}
        envelope.user = self.user
        identifier.Add().apply(envelope)
        bounces.Check().apply(envelope)
        sending_domain.Check().apply(envelope)
        store_mail.Store().apply(envelope)

        self.client.post(
            '/h/subscriptions/{}/optout/'.format(
                envelope.headers.get(
                    settings.TRANSACTIONAL['X_MESSAGE_ID_HEADER'])))

        another_smtp_application = SmtpApplicationFactory()
        SendingDomainFactory(
            name='example.com',
            organization=another_smtp_application.author.organization)
        headers = (
            'From: test-from@example.com\n'
            'Subject: foo\n'
            'To: foo@bar\n'
            '{}: test').format(
                settings.TRANSACTIONAL['X_MAIL_BATCH_HEADER'])
        recipient = faker.email()
        envelope = self.mk_envelope(
            headers.encode('utf-8'),
            sender=faker.email(), recipients=[recipient])
        envelope.client = {'auth': (another_smtp_application.username, None)}
        envelope.user = self.user
        identifier.Add().apply(envelope)
        bounces.Check().apply(envelope)
        sending_domain.Check().apply(envelope)
        store_mail.Store().apply(envelope)

    def test_optout_batch_with_category(self):
        # First Optout on mail without category
        headers = (
            'From: test-from@example.com\n'
            'Subject: foo\n'
            'To: foo@bar\n'
            '{}: test').format(
                settings.TRANSACTIONAL['X_MAIL_BATCH_HEADER'])
        recipient = faker.email()
        envelope = self.mk_envelope(
            headers.encode('utf-8'),
            sender=faker.email(), recipients=[recipient])
        envelope.client = {'auth': (self.smtp_application.username, None)}
        envelope.user = self.user
        identifier.Add().apply(envelope)
        bounces.Check().apply(envelope)
        sending_domain.Check().apply(envelope)
        store_mail.Store().apply(envelope)

        self.client.post(
            '/h/subscriptions/{}/optout/'.format(
                envelope.headers.get(
                    settings.TRANSACTIONAL['X_MESSAGE_ID_HEADER'])))

        # Second one with same recipient but with a category
        headers = (
            'From: test-from@example.com\n'
            'Subject: foo\n'
            'To: foo@bar\n'
            '{}: test-category\n'
            '{}: test').format(
                settings.TRANSACTIONAL['X_MAIL_BATCH_CATEGORY_HEADER'],
                settings.TRANSACTIONAL['X_MAIL_BATCH_HEADER'])
        envelope = self.mk_envelope(
            headers.encode('utf-8'),
            sender=faker.email(), recipients=[recipient])
        envelope.client = {'auth': (self.smtp_application.username, None)}
        envelope.user = self.user
        identifier.Add().apply(envelope)
        bounces.Check().apply(envelope)
        sending_domain.Check().apply(envelope)
        store_mail.Store().apply(envelope)

        identifier.Add().apply(envelope)
        bounces.Check().apply(envelope)


class TestReturnPath(PolicyCase):
    def test_no_prev_returnpath(self):
        """
        X-Munch-HTTP-Return-Path: yes
        Return-Path: no

        Return-Path-Rewrite: yes
        """
        env = self.mk_envelope(b'X-Munch-HTTP-Return-Path: http://unittest')
        headers_policy.RewriteReturnPath().apply(env)
        headers, _ = env.flatten()
        self.assertIn('return-', env.sender)

    def test_no_prev_returnpath_without_http_returnpath(self):
        """
        X-Munch-HTTP-Return-Path: no
        Return-Path: no

        Return-Path: envelope.sender
        """
        env = self.mk_envelope(b'', sender="foo@bar.com")
        headers_policy.RewriteReturnPath().apply(env)
        headers, _ = env.flatten()
        self.assertIn('foo@bar.com', env.sender)

    def test_replace_returnpath(self):
        """
        X-Munch-HTTP-Return-Path: yes
        Return-Path: yes

        Return-Path-Rewrite: yes
        """
        env = self.mk_envelope(
            b"X-Munch-HTTP-Return-Path: http://unittest.example.com/ping",
            sender='rp-124@example.com')
        headers_policy.RewriteReturnPath().apply(env)
        headers, _ = env.flatten()

        self.assertRegex(env.sender, 'return-.*test.munch.example.com.*')

    def test_replace_returnpath_without_http_returnpath(self):
        """
        X-Munch-HTTP-Return-Path: no
        Return-Path: yes

        Return-Path-Rewrite: no
        """
        env = self.mk_envelope(b"Return-Path: rp-1234@example.com")
        headers_policy.RewriteReturnPath().apply(env)
        headers, _ = env.flatten()

        self.assertIn(
            'Return-Path: rp-1234@example.com', headers.decode('utf-8'))
