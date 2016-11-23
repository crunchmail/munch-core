import datetime

from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from libfaketime import fake_time
from faker import Factory as FakerFactory

from munch.apps.users.tests.factories import UserFactory
from munch.apps.optouts.tests.factories import OptOutFactory

from ..models import Mail
from ..models import OptOut
from ..models import Message
from ..models import MailStatus

from .factories import MailFactory
from .factories import MessageFactory
from .factories import MailStatusFactory

faker = FakerFactory.create()


class MailManagerTest(TestCase):
    def setUp(self):
        self.user = UserFactory()

        self.message = MessageFactory(status='message_ok', author=self.user)

        mail = MailFactory(message=self.message)
        MailStatusFactory(mail=mail)
        MailStatusFactory(mail=mail, status='sending')
        MailStatusFactory(mail=mail, status='delivered')

        mail = MailFactory(message=self.message)
        MailStatusFactory(mail=mail)
        MailStatusFactory(mail=mail, status='sending')
        MailStatusFactory(mail=mail, status='bounced')

        mail = MailFactory(message=self.message)
        MailStatusFactory(mail=mail)
        MailStatusFactory(mail=mail, status='sending')
        MailStatusFactory(mail=mail, status='dropped', raw_msg='greylisted')
        MailStatusFactory(mail=mail, status='dropped', raw_msg='greylisted')

    def test_all_legit(self):
        legit_objs = set(self.message.mails.legit_for(self.message))

        all_objs = set(self.message.mails.all())
        self.assertEqual(legit_objs, all_objs)

    def test_legit_some_optout(self):
        mail = self.message.mails.first()
        OptOutFactory(
            author=self.message.author, category=self.message.category,
            identifier=mail.identifier, address=mail.recipient)

        legit_objs = set(self.message.mails.legit_for(self.message))
        all_objs = set(self.message.mails.all())

        self.assertIn(mail, all_objs)
        self.assertNotIn(mail, legit_objs)

    def test_legit_some_optout_override(self):
        mail = self.message.mails.first()
        OptOutFactory(
            author=self.message.author, category=self.message.category,
            identifier=mail.identifier, address=mail.recipient)

        legit_objs = set(self.message.mails.legit_for(
            self.message, include_optouts=True))
        all_objs = set(self.message.mails.all())

        self.assertEqual(legit_objs, all_objs)

    def test_legit_some_bounce_optout_override(self):
        # Change the optout type to bounce
        mail = self.message.mails.filter(curstatus='delivered').first()
        opt_out = OptOutFactory(
            identifier=mail.identifier,
            address=mail.recipient,
            origin=OptOut.BY_BOUNCE)

        # add a mail coresponding to an optout on a previous message
        # jane has two reasons not to receive the mail :
        # bounce-optout+regular-optout
        message = MessageFactory(author=self.user)
        MailFactory(recipient=mail.recipient, message=message)
        legit_objs = set(self.message.mails.legit_for(
            self.message, include_optouts=True, include_bounces=True))
        all_objs = set(self.message.mails.all())

        self.assertEqual(legit_objs, all_objs)

    def test_legit_some_bounce_optout(self):
        # Change the optout type to bounce
        mail = self.message.mails.filter(curstatus='bounced').first()
        opt_out = OptOutFactory(
            identifier=mail.identifier,
            address=mail.recipient,
            origin=OptOut.BY_BOUNCE)

        message = MessageFactory(author=self.user)

        # add a mail coresponding to an optout on a previous message
        # jane has two reasons not to receive the mail :
        # bounce-optout+regular-optout
        MailFactory(recipient=mail.recipient, message=message)
        legit_objs = set(self.message.mails.legit_for(
            self.message, include_optouts=True))
        all_objs = set(self.message.mails.all())

        self.assertNotEqual(legit_objs, all_objs)

    def test_done(self):
        self.assertEqual(Mail.objects.done().count(), 3)

    def test_pending(self):
        message = MessageFactory(status='message_ok', author=self.user)

        mail_1 = MailFactory(message=message)
        MailStatusFactory(mail=mail_1)
        MailStatusFactory(mail=mail_1, status=MailStatus.SENDING)

        mail_2 = MailFactory(message=message)
        MailStatusFactory(mail=mail_2)
        MailStatusFactory(mail=mail_2, status=MailStatus.SENDING)

        mail_3 = MailFactory(message=message)
        MailStatusFactory(mail=mail_3)
        MailStatusFactory(mail=mail_3, status=MailStatus.SENDING)
        MailStatusFactory(mail=mail_3, status=MailStatus.DELIVERED)

        self.assertEqual(Mail.objects.filter(
            pk__in=[mail_1.pk, mail_2.pk, mail_3.pk]).pending().count(), 2)

    def test_with_bounds(self):
        Mail.objects.all().delete()
        Message.objects.all().delete()
        MailStatus.objects.all().delete()

        with fake_time('2016-10-10 08:00:00'):
            message = MessageFactory(status='message_ok', author=self.user)
            mail_1 = MailFactory(message=message)
            mail_2 = MailFactory(message=message)
            mail_3 = MailFactory(message=message)

        with fake_time('2016-10-10 08:00:05'):
            MailStatusFactory(mail=mail_1)
            MailStatusFactory(mail=mail_2)
            MailStatusFactory(mail=mail_3)
        with fake_time('2016-10-10 08:00:07'):
            MailStatusFactory(mail=mail_1, status=MailStatus.SENDING)
            MailStatusFactory(mail=mail_2, status=MailStatus.SENDING)
            MailStatusFactory(mail=mail_3, status=MailStatus.SENDING)
        with fake_time('2016-10-10 08:00:57'):
            MailStatusFactory(mail=mail_1, status=MailStatus.DELIVERED)
            MailStatusFactory(mail=mail_2, status=MailStatus.BOUNCED)
            MailStatusFactory(mail=mail_3, status=MailStatus.DROPPED)

        qs = Mail.objects.with_bounds().filter(
            curstatus=MailStatus.BOUNCED).first()
        with fake_time('2016-10-10 08:00:00'):
            self.assertEqual(qs.start, timezone.now())

        with fake_time('2016-10-10 08:00:57'):
            self.assertEqual(qs.end, timezone.now())

        self.assertEqual(qs.delivery_duration.total_seconds(), 57.0)

    def test_median(self):
        with fake_time('2016-10-10 08:00:00'):
            mail_1 = MailFactory(message=self.message)
            mail_2 = MailFactory(message=self.message)
            MailStatusFactory(mail=mail_1)
            MailStatusFactory(mail=mail_2)
        with fake_time('2016-10-10 08:00:05'):
            MailStatusFactory(mail=mail_1, status='sending')
            MailStatusFactory(mail=mail_2, status='sending')
        with fake_time('2016-10-10 08:00:30'):
            MailStatusFactory(mail=mail_1, status='delivered')
        with fake_time('2016-10-10 08:01:00'):
            MailStatusFactory(mail=mail_2, status='delivered')
        median = Mail.objects.filter(
            pk__in=[mail_1.pk, mail_2.pk]).median('delivery_duration')
        self.assertEqual(median, datetime.timedelta(seconds=45))

    def test_median_zeroitem(self):
        median = Mail.objects.none().median('delivery_duration')
        self.assertEqual(median, datetime.timedelta())

    def test_had_delay(self):
        now = timezone.now()

        mail_1 = MailFactory(message=self.message)
        mail_2 = MailFactory(message=self.message)
        self.message.status = Message.SENDING
        self.message.save()

        MailStatusFactory(
            mail=mail_1, status=MailStatus.DELIVERED,
            creation_date=now + datetime.timedelta(minutes=5))
        MailStatusFactory(
            mail=mail_2, status=MailStatus.DROPPED,
            creation_date=now + datetime.timedelta(minutes=5))

        mail_1 = Mail.objects.get(pk=mail_1.pk)
        mail_2 = Mail.objects.get(pk=mail_2.pk)
        self.assertEqual(mail_1.had_delay, False)
        self.assertEqual(mail_2.had_delay, True)

    def test_update_cached_fields(self):
        with fake_time('2016-10-10 08:00:00'):
            mail = MailFactory(
                recipient=faker.email(), message=self.message)
            now = timezone.now()
            d = now
            for status in [
                    MailStatus.QUEUED, MailStatus.SENDING, MailStatus.DROPPED]:
                MailStatusFactory(
                    mail=mail, status=status, creation_date=d, raw_msg='test1')
                d = now + datetime.timedelta(minutes=5)

        Mail.objects.update(
            latest_status_date=None, first_status_date=None,
            delivery_duration=None, curstatus=MailStatus.SENDING)
        Mail.objects.filter(message=self.message).update_cached_fields()

        mail = Mail.objects.get(pk=mail.pk)
        self.assertEqual(mail.delivery_duration.total_seconds(), 300)
        self.assertEqual(
            mail.latest_status_date, now + datetime.timedelta(minutes=5))
        self.assertEqual(mail.first_status_date, now)
        self.assertEqual(mail.curstatus, MailStatus.DROPPED)
        self.assertEqual(mail.had_delay, True)

    def test_mail_with_source(self):
        self.message.mails.all().delete()

        MailFactory(
            message=self.message, source_type='zim-bra', source_ref='list-42')

    def test_mail_with_properties(self):
        self.message.mails.all().delete()

        mail_1 = MailFactory(message=self.message, properties={'gender': 'm'})
        MailFactory(message=self.message, properties={'gender': 'f'})

        filtered = Mail.objects.filter(properties__gender='m')
        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().recipient, mail_1.recipient)

    def test_mail_with_bad_source_format(self):
        self.message.mails.all().delete()

        with self.assertRaises(ValidationError):
            m = MailFactory(
                message=self.message,
                source_type='zim bra',
                source_ref='list-42')
            m.full_clean()
