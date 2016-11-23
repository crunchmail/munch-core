from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.test.utils import override_settings

from munch.apps.users.tests.factories import UserFactory

from ..models import MailStatus

from .factories import MailFactory
from .factories import MessageFactory
from .factories import MailStatusFactory


class MailStatusManagerTest(TestCase):
    def test_duration_zeroitem(self):
        self.assertEqual(MailStatus.objects.none().duration(), timedelta())


class MailStatusTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)
        self.mail = MailFactory(message=self.message)
        MailStatusFactory(mail=self.mail, status=MailStatus.QUEUED)
        MailStatusFactory(mail=self.mail, status=MailStatus.SENDING)

    def test_match_policy_ok(self):
        mail_status = MailStatusFactory(
            mail=self.mail, status=MailStatus.BOUNCED, status_code='5.1.1')
        ok_policy = (['6.', '5.'], 3, 1)
        self.assertTrue(mail_status.match_policy(ok_policy))

    def test_match_policy_empty(self):
        mail_status = MailStatusFactory(
            mail=self.mail, status=MailStatus.BOUNCED,
            creation_date=timezone.now(), status_code='5.1.1')
        ok_policy = ([''], 3, 1)
        self.assertTrue(mail_status.match_policy(ok_policy))

    def test_nomatch_policy_code(self):
        mail_status = MailStatusFactory(
            mail=self.mail, status=MailStatus.BOUNCED,
            creation_date=timezone.now(), status_code='5.1.1')
        othercode_policy = (['3.'], 3, 1)
        self.assertFalse(mail_status.match_policy(othercode_policy))

    def test_nomatch_policy_date(self):
        mail_status = MailStatusFactory(
            mail=self.mail, status=MailStatus.BOUNCED,
            creation_date=timezone.now() - timedelta(days=2),
            status_code='5.1.1')
        tooold_policy = (['5.'], 3, 1)
        self.assertFalse(mail_status.match_policy(tooold_policy))

    @override_settings(BOUNCE_POLICY=[(['5.'], 3, 1)])
    def test_should_optout(self):
        user = UserFactory()

        def mk_message(i):
            message = MessageFactory(author=user)
            mail = MailFactory(recipient='i@example.com', message=message)

            MailStatusFactory(
                status=MailStatus.QUEUED, raw_msg='queued',
                mail=mail, status_code='5.1.1')
            MailStatusFactory(
                status=MailStatus.SENDING, raw_msg='sent',
                mail=mail, status_code='5.1.1')
            return MailStatusFactory(
                status=MailStatus.BOUNCED, raw_msg='Hardbounced',
                mail=mail, status_code='5.1.1')

        b1 = mk_message(1)
        self.assertFalse(b1.should_optout())
        b2 = mk_message(2)
        self.assertFalse(b2.should_optout())
        b3 = mk_message(3)
        self.assertTrue(b3.should_optout())
