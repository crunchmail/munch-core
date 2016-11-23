import unittest
from datetime import datetime
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils.timezone import utc
from django.test.utils import override_settings
from libfaketime import fake_time

from munch.core.utils.tests import temporary_settings
from munch.apps.users.tests.factories import UserFactory

from ..tasks import handle_dsn
from ..tasks import handle_fbl
from ..tasks import handle_mail_optout
from ..models import Mail
from ..models import OptOut
from ..models import Message
from ..models import MailStatus

from .factories import MailFactory
from .factories import MessageFactory
from .factories import MailStatusFactory


@override_settings(
    SKIP_SPAM_CHECK=False, SPAMD_SERVICE_NAME='dne.example.com',
    SPAMD_HOST='dne.example.com')
class DSNQTests(TestCase):
    """
    SPAMD_SERVICE_NAME is set to something wrong
    to be sure it never gets called
    """
    def setUp(self):
        cache.clear()
        # To start testing DSN status, we have first to simulate that the mail
        # has been passed to infrastructure.
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)

        self.mail_1 = MailFactory(message=self.message)
        self.mail_2 = MailFactory(message=self.message)

        details = (
            (self.mail_1, MailStatus.QUEUED, datetime(
                2014, 8, 5, 22, tzinfo=utc) + timedelta(minutes=5)),
            (self.mail_1, MailStatus.SENDING, datetime(
                2014, 8, 6, 22, tzinfo=utc)),
            (self.mail_2, MailStatus.QUEUED, datetime(
                2014, 8, 5, 22, tzinfo=utc) + timedelta(minutes=5)),
            (self.mail_2, MailStatus.SENDING, datetime(
                2014, 8, 6, 22, tzinfo=utc)))

        for mail, status, date in details:
            MailStatusFactory(
                mail=mail, status=status, creation_date=date, raw_msg=status)

        self.hardbounce_message = (
            "smtp; 550 5.1.1 <nonexist@example.com>: Recipient address"
            "rejected: User unknown in virtual mailbox table")

    def test_mail_msg_ok(self):
        with fake_time('Fri,  5 Aug 2014 23:35:52 +0700 (WIT)'):
            handle_dsn(
                'To: return-{}@test.munch.example.com'.format(
                    self.mail_1.identifier),
                {
                    'Final-Recipient': self.mail_1.recipient,
                    'Diagnostic-Code': 'Delivered',
                    'Status': '2.0.0',
                    'Arrival-Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'})
        self.mail_1 = Mail.objects.get(pk=self.mail_1.pk)
        self.assertEqual(self.mail_1.curstatus, MailStatus.DELIVERED)

        last_status = self.mail_1.statuses.last()
        self.assertEqual(last_status.status, MailStatus.DELIVERED)
        self.assertEqual(
            last_status.creation_date, datetime(
                2014, 8, 5, 21, 35, 52,
                tzinfo=last_status.creation_date.tzinfo))
        self.assertEqual(last_status.mail, self.mail_1)
        self.assertEqual(last_status.raw_msg, 'Delivered')
        self.assertEqual(last_status.status_code, '2.0.0')

    def test_mail_msg_to_protected(self):
        """ Check that we extract the To from optional surounding "<" ">"
        """
        with fake_time('Fri,  5 Aug 2014 23:35:52 +0700 (WIT)'):
            handle_dsn(
                'To: A A <return-{}@test.munch.example.com>'.format(
                    self.mail_1.identifier),
                {
                    'Final-Recipient': self.mail_1.recipient,
                    'Diagnostic-Code': 'Delivered',
                    'Status': '2.0.0',
                    'Arrival-Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'})
        self.mail_1 = Mail.objects.get(pk=self.mail_1.pk)
        self.assertEqual(self.mail_1.curstatus, MailStatus.DELIVERED)

    def test_mail_msg_hard(self):
        handle_dsn(
            'To: return-{}@test.munch.example.com'.format(self.mail_1.identifier),
            {
                'Final-Recipient': self.mail_1.recipient,
                'Diagnostic-Code': self.hardbounce_message,
                'Status': '5.1.1',
                'Arrival-Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'})
        self.mail_1 = Mail.objects.get(pk=self.mail_1.pk)
        self.assertEqual(self.mail_1.curstatus, MailStatus.BOUNCED)

        last_status = self.mail_1.statuses.last()
        self.assertEqual(last_status.status, MailStatus.BOUNCED)
        self.assertEqual(
            last_status.raw_msg, self.hardbounce_message.replace('\n', ' '))

    def test_mail_msg_soft(self):
        handle_dsn(
            'To: return-{}@test.munch.example.com'.format(self.mail_1.identifier),
            {
                'Final-Recipient': self.mail_1.recipient,
                'Action': 'Failed',
                'Diagnostic-Code': 'SoftBounce',
                'Status': '4.1.1',
                'Arrival-Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'})
        self.mail_1 = Mail.objects.get(pk=self.mail_1.pk)
        self.assertEqual(self.mail_1.curstatus, MailStatus.DROPPED)

        last_status = self.mail_1.statuses.last()
        self.assertEqual(last_status.status, MailStatus.DROPPED)
        self.assertEqual(last_status.raw_msg, 'SoftBounce')

    def test_mail_msg_soft_notify(self):
        """ Quite rare setup where the MTA nofifies the envelope-from

        when its message is being requeued.
        """
        handle_dsn(
            'To: return-{}@test.munch.example.com'.format(self.mail_1.identifier),
            {
                'Final-Recipient': self.mail_1.recipient,
                'Action': 'delayed',
                'Diagnostic-Code': 'SoftBounce',
                'Status': '4.1.1',
                'Arrival-Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'})
        self.mail_1 = Mail.objects.get(pk=self.mail_1.pk)
        self.assertEqual(self.mail_1.curstatus, MailStatus.DELAYED)

        last_status = self.mail_1.statuses.last()
        self.assertEqual(last_status.status, MailStatus.DELAYED)
        self.assertEqual(last_status.raw_msg, 'SoftBounce')

    def test_last_mail_change_status(self):
        self.message.status = 'sending'
        self.message.save()

        handle_dsn(
            'To: return-{}@test.munch.example.com'.format(self.mail_1.identifier),
            {
                'Final-Recipient': self.mail_1.recipient,
                'Diagnostic-Code': 'Delivered',
                'Status': '2.0.0',
                'Arrival-Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'})
        self.assertEqual(self.message.status, Message.SENDING)
        handle_dsn(
            'To: return-{}@test.munch.example.com'.format(self.mail_2.identifier),
            {
                'Final-Recipient': self.mail_2.recipient,
                'Diagnostic-Code': self.hardbounce_message,
                'Status': '5.1.1',
                'Arrival-Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'})
        self.message = Message.objects.get(pk=self.message.pk)
        self.assertEqual(self.message.status, Message.SENT)
        self.assertIsNotNone(self.message.completion_date)

    def test_bounce_after_delivered(self):
        """
        Test that we can become « softbounced » after having been « delivered »

        That's strange, but may happen if an intermediary server ack the
        message and the final one bounce it with backscatter.
        """
        handle_dsn(
            'To: return-{}@test.munch.example.com'.format(self.mail_1.identifier),
            {
                'Final-Recipient': self.mail_1.recipient,
                'Diagnostic-Code': 'Delivered',
                'Status': '2.0.0',
                'Arrival-Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'})
        handle_dsn(
            'To: return-{}@test.munch.example.com'.format(self.mail_1.identifier),
            {
                'Final-Recipient': self.mail_1.recipient,
                'Diagnostic-Code': self.hardbounce_message,
                'Status': '5.1.1',
                'Arrival-Date': 'Fri,  5 Aug 2014 23:50:50 +0700 (WIT)'})
        self.mail_1 = Mail.objects.get(pk=self.mail_1.pk)
        self.assertEqual(self.mail_1.curstatus, MailStatus.BOUNCED)

        last_status = self.mail_1.statuses.last()
        self.assertEqual(last_status.status, MailStatus.BOUNCED)
        self.assertEqual(
            last_status.raw_msg, self.hardbounce_message.replace('\n', ' '))

    @override_settings(BOUNCE_POLICY=[(['5.'], 3, 365)])
    def test_several_bounce_imply_optout(self):
        """ Make an optout after a certain of ammount of bounce is recvd"""
        user = UserFactory()

        def mk_message(i):
            with self.settings(SKIP_SPAM_CHECK=True):
                message = MessageFactory(author=user)
                message.status = Message.MSG_OK
                message.save()
                message.status = Message.SENDING
                message.save()
                mail = MailFactory(message=message, recipient='i@example.com')

                # Simulate it has been passed to infrastructure
                MailStatusFactory(
                    mail=mail, status=MailStatus.QUEUED,
                    raw_msg='sent by local MTA',
                    creation_date=datetime(2014, 8, 4, tzinfo=utc))
                MailStatusFactory(
                    mail=mail, status=MailStatus.SENDING,
                    raw_msg='sent by local MTA',
                    creation_date=datetime(2014, 8, 4, tzinfo=utc))

            handle_dsn(
                'To: {}'.format(mail.envelope_from),
                {
                    'Final-Recipient': 'i@example.com',
                    'Diagnostic-Code': self.hardbounce_message,
                    'Status': '5.1.1',
                    'Arrival-Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'})

        optout = OptOut.objects.filter(address='i@example.com')

        mk_message(1)
        self.assertFalse(optout.exists())
        mk_message(2)
        self.assertFalse(optout.exists())
        mk_message(3)
        self.assertTrue(optout.exists())

    def test_fbl_optout(self):
        main_headers = (
            'To: abuse@test.munch.example.com\n'
            'Date: Fri,  5 Aug 2014 23:35:50 +0700 (WIT)')
        orig_headers = {
            'Return-Path': 'return-{}@test.munch.example.com'.format(
                self.mail_1.identifier)}
        feedback_headers = {
            'Feedback-Type': 'abuse',
            'User-Agent': 'unittest',
            'Version': '0.1'}
        handle_fbl(main_headers, orig_headers, feedback_headers)

        optout = OptOut.objects.get(identifier=self.mail_1.identifier)
        d = datetime(
            2014, 8, 5, 16, 35, 50, tzinfo=optout.creation_date.tzinfo)

        self.assertEqual(optout.creation_date, d)
        self.assertEqual(optout.origin, OptOut.BY_FBL)

    def test_mail_optout(self):
        headers = {
            'To': 'unsubscribe-{}@test.munch.example.com'.format(
                self.mail_1.identifier),
            'Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'}
        handle_mail_optout(headers)

        optout = OptOut.objects.get(identifier=self.mail_1.identifier)
        d = datetime(
            2014, 8, 5, 16, 35, 50, tzinfo=optout.creation_date.tzinfo)
        self.assertEqual(optout.creation_date, d)
        self.assertEqual(optout.origin, OptOut.BY_MAIL)

    def test_mail_multiple_optout(self):
        """ Try to send multiple optout. Second one must be ignored. """
        headers = {
            'To': 'unsubscribe-{}@test.munch.example.com'.format(
                self.mail_1.identifier),
            'Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'}
        handle_mail_optout(headers)
        headers = {
            'To': 'unsubscribe-{}@test.munch.example.com'.format(
                self.mail_1.identifier),
            'Date': 'Fri,  5 Aug 2014 23:37:50 +0700 (WIT)'}

        handle_mail_optout(headers)
        optout = OptOut.objects.get(identifier=self.mail_1.identifier)
        d = datetime(
            2014, 8, 5, 16, 35, 50, tzinfo=optout.creation_date.tzinfo)
        self.assertEqual(optout.creation_date, d)
        self.assertEqual(optout.origin, OptOut.BY_MAIL)

    @unittest.skip('Missing test')
    def test_invalid_data_reject(self):
        """ Invalid data should trigger logging and rejecting
        """
        pass

    @unittest.skip('Missing test')
    def test_invalid_transition_reject(self):
        """ Invalid data should trigger logging and rejecting
        """
        pass
