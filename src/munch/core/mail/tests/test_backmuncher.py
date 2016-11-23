import os
import email
from unittest import TestCase

from django.conf import settings
from slimta.queue import QueueError
from slimta.envelope import Envelope

from munch.apps.users.tests.factories import UserFactory
from munch.apps.campaigns.tests.factories import MailFactory
from munch.apps.campaigns.tests.factories import MessageFactory
from munch.apps.campaigns.models import get_base_mail_identifier
from munch.apps.transactional.models import get_mail_identifier

from ..backmuncher import DSNHandler
from ..backmuncher import ARFHandler
from ..backmuncher import UnsubscribeHandler
from ..backmuncher import BackMuncherQueuePolicy

UNSUBSCRIBE_EMAIL=open(os.path.join(
    os.path.dirname(__file__), 'samples/unsubscribe.eml')).read()
DSN_REPORT=open(os.path.join(
    os.path.dirname(__file__), 'samples/dsn_ok.eml')).read()
ARF_REPORT=open(os.path.join(
    os.path.dirname(__file__), 'samples/arf_abuse.eml')).read()


class TestSamples(TestCase):
    def test_multipart(self):
        arf = ARF_REPORT.replace('||FROM||', 'foo@bar')
        arf = arf.replace('||RETURNPATH||', 'foo@bar')
        dsn = DSN_REPORT.replace('||TO||', 'foo@bar')
        dsn = dsn.replace('||RETURNPATH||', 'foo@bar')
        self.assertTrue(email.message_from_string(arf).is_multipart())
        self.assertTrue(email.message_from_string(dsn).is_multipart())

    def test_multipart(self):
        dsn = DSN_REPORT.replace('||TO||', 'foo@bar')
        dsn = dsn.replace('||RETURNPATH||', 'foo@bar')
        m = email.message_from_string(dsn)
        self.assertIsNotNone(m['Subject'])
        self.assertTrue(m.is_multipart())


class RecipientTestCase(TestCase):
    def test_valid_recipient(self):
        recipient = 'foo@test.munch.example.com'
        dsn = DSN_REPORT.replace('||TO||', recipient)
        dsn = dsn.replace('||RETURNPATH||', 'foo@bar')
        message = email.message_from_string(dsn)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        with self.assertRaises(QueueError) as exc:
            BackMuncherQueuePolicy().apply(envelope)
        self.assertNotEqual(str(exc.exception), 'Missing recipient')

    def test_invalid_recipient(self):
        recipient = 'foo@test.munch.example.com'
        dsn = DSN_REPORT.replace('||TO||', recipient)
        dsn = dsn.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(dsn)
        envelope = Envelope()
        envelope.parse_msg(message)
        with self.assertRaises(QueueError) as exc:
            BackMuncherQueuePolicy().apply(envelope)
        self.assertEqual(str(exc.exception), 'Missing recipient')


class ReturnPathDomainTestCase(TestCase):
    def test_valid_return_path(self):
        recipient = 'foo@test.munch.example.com'
        dsn = DSN_REPORT.replace('||TO||', recipient)
        dsn = dsn.replace('||RETURNPATH||', 'foo@bar')
        message = email.message_from_string(dsn)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        with self.assertRaises(QueueError) as exc:
            BackMuncherQueuePolicy().apply(envelope)
        self.assertNotEqual(str(exc.exception), 'Domain not valid')

    def test_invalid_return_path(self):
        recipient = 'foo@bar'
        dsn = DSN_REPORT.replace('||TO||', recipient)
        dsn = dsn.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(dsn)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        with self.assertRaises(QueueError) as exc:
            BackMuncherQueuePolicy().apply(envelope)
        self.assertEqual(str(exc.exception), 'Domain not valid')


class PrefixTestCase(TestCase):
    def test_valid_prefix(self):
        recipient = 'return-foo@test.munch.example.com'
        dsn = DSN_REPORT.replace('||TO||', recipient)
        dsn = dsn.replace('||RETURNPATH||', 'foo@bar')
        message = email.message_from_string(dsn)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        BackMuncherQueuePolicy().apply(envelope)

    def test_invalid_prefix(self):
        recipient = 'foo@test.munch.example.com'
        dsn = DSN_REPORT.replace('||TO||', recipient)
        dsn = dsn.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(dsn)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        with self.assertRaises(QueueError) as exc:
            BackMuncherQueuePolicy().apply(envelope)
        self.assertEqual(str(exc.exception), 'Prefix not allowed')


class DSNHandlerTestCase(TestCase):
    def test_parse(self):
        recipient = 'return-{}@test.munch.example.com'.format(
            get_mail_identifier())
        dsn = DSN_REPORT.replace('||TO||', recipient)
        dsn = dsn.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(dsn)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = DSNHandler(envelope, message)

        main_headers = email.message_from_string(handler.message.as_string())
        report_headers = handler.get_report()

        self.assertEqual(main_headers['To'], recipient)

        self.assertEqual(
            report_headers['Arrival-Date'],
            'Mon,  1 Sep 2014 17:36:45 +0000 (UTC)')
        self.assertEqual(report_headers['Diagnostic-Code'], 'smtp; 250 OK')
        self.assertEqual(report_headers['Status'], '2.0.0')
        self.assertEqual(report_headers['Action'], 'relayed')

    def test_invalide_recipient(self):
        recipient = 'return-foo@test.munch.example.com'
        dsn = DSN_REPORT.replace('||TO||', recipient)
        dsn = dsn.replace('||RETURNPATH||', 'foo@bar')
        message = email.message_from_string(dsn)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = DSNHandler(envelope, message)
        self.assertIsNone(handler.apply())

    def test_unknown_identifier(self):
        recipient = 'return-{}@test.munch.example.com'.format(
            get_base_mail_identifier())
        dsn = DSN_REPORT.replace('||TO||', recipient)
        dsn = dsn.replace('||RETURNPATH||', 'foo@bar')
        message = email.message_from_string(dsn)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = DSNHandler(envelope, message)
        self.assertIsNone(handler.apply())

        recipient = 'return-{}@test.munch.example.com'.format(
            get_mail_identifier())
        dsn = DSN_REPORT.replace('||TO||', recipient)
        dsn = dsn.replace('||RETURNPATH||', 'foo@bar')
        message = email.message_from_string(dsn)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = DSNHandler(envelope, message)
        self.assertIsNone(handler.apply())

    def test_valid_dsn(self):
        user = UserFactory()
        message = MessageFactory(author=user)
        mail = MailFactory(message=message)

        recipient = 'return-{}@test.munch.example.com'.format(
            mail.identifier)
        dsn = DSN_REPORT.replace('||TO||', recipient)
        dsn = dsn.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(dsn)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = DSNHandler(envelope, message)
        self.assertIsNotNone(handler.apply())


class ARFHandlerTestCase(TestCase):
    def test_parse(self):
        recipient = 'return-{}@test.munch.example.com'.format(
            get_mail_identifier())
        arf = ARF_REPORT.replace('||TO||', recipient)
        arf = arf.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(arf)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = ARFHandler(envelope, message)

        main_headers = email.message_from_string(handler.message.as_string())
        orig_headers = handler.get_original()
        report_headers = handler.get_report()

        self.assertEqual(orig_headers['Return-Path'], recipient)
        self.assertEqual(report_headers['Feedback-Type'], 'abuse')
        self.assertEqual(main_headers['Date'], 'Thu, 8 Mar 2005 17:40:36 EDT')

    def test_invalide_returnpath(self):
        recipient = 'return-foo@test.munch.example.com'
        arf = ARF_REPORT.replace('||TO||', 'abuse@test.munch.example.com')
        arf = arf.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(arf)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = ARFHandler(envelope, message)
        self.assertIsNone(handler.apply())

    def test_unknown_identifier(self):
        recipient = 'return-{}@test.munch.example.com'.format(
            get_base_mail_identifier())
        arf = ARF_REPORT.replace('||TO||', 'abuse@test.munch.example.com')
        arf = arf.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(arf)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = ARFHandler(envelope, message)
        self.assertIsNone(handler.apply())

        recipient = 'return-{}@test.munch.example.com'.format(
            get_mail_identifier())
        arf = ARF_REPORT.replace('||TO||', 'abuse@test.munch.example.com')
        arf = arf.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(arf)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = ARFHandler(envelope, message)
        self.assertIsNone(handler.apply())

    def test_valid_arf(self):
        user = UserFactory()
        message = MessageFactory(author=user)
        mail = MailFactory(message=message)

        recipient = 'return-{}@test.munch.example.com'.format(
            mail.identifier)
        arf = ARF_REPORT.replace('||TO||', 'abuse@test.munch.example.com')
        arf = arf.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(arf)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = ARFHandler(envelope, message)
        self.assertIsNotNone(handler.apply())


class UnsubscribeHandlerTestCase(TestCase):
    def test_parse(self):
        recipient = 'unsubscribe-{}@test.munch.example.com'.format(
            get_mail_identifier())
        unsubscribe = UNSUBSCRIBE_EMAIL.replace('||TO||', recipient)
        unsubscribe = unsubscribe.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(unsubscribe)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = UnsubscribeHandler(envelope, message)

        main_headers = dict(handler.message)

        self.assertEqual(main_headers['To'], recipient)

    def test_invalide_returnpath(self):
        recipient = 'return-foo@test.munch.example.com'
        unsubscribe = UNSUBSCRIBE_EMAIL.replace('||TO||', recipient)
        unsubscribe = unsubscribe.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(unsubscribe)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = UnsubscribeHandler(envelope, message)
        self.assertIsNone(handler.apply())

    def test_unknown_identifier(self):
        recipient = 'return-{}@test.munch.example.com'.format(
            get_base_mail_identifier())
        unsubscribe = UNSUBSCRIBE_EMAIL.replace('||TO||', recipient)
        unsubscribe = unsubscribe.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(unsubscribe)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = UnsubscribeHandler(envelope, message)
        self.assertIsNone(handler.apply())

        recipient = 'return-{}@test.munch.example.com'.format(
            get_mail_identifier())
        unsubscribe = UNSUBSCRIBE_EMAIL.replace('||TO||', recipient)
        unsubscribe = unsubscribe.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(unsubscribe)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = UnsubscribeHandler(envelope, message)
        self.assertIsNone(handler.apply())

    def test_valid_unsubscribe(self):
        user = UserFactory()
        message = MessageFactory(author=user)
        mail = MailFactory(message=message)

        recipient = 'unsubscribe-{}@test.munch.example.com'.format(
            mail.identifier)
        unsubscribe = UNSUBSCRIBE_EMAIL.replace('||TO||', recipient)
        unsubscribe = unsubscribe.replace('||RETURNPATH||', recipient)
        message = email.message_from_string(unsubscribe)
        envelope = Envelope()
        envelope.parse_msg(message)
        envelope.recipients = [recipient]
        handler = UnsubscribeHandler(envelope, message)
        self.assertIsNotNone(handler.apply())
