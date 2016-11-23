from django.test import TestCase

from munch.apps.users.tests.factories import UserFactory
from munch.apps.transactional.models import Mail as TransactionalMail

from ..models import RawMail
from ..tasks import purge_raw_mail


class PurgeRawMailTestCase(TestCase):
    def test_all(self):
        user = UserFactory()

        raw_mail_01, _ = RawMail.objects.get_or_create(content='test 01')
        raw_mail_02, _ = RawMail.objects.get_or_create(content='test_02')

        mail_01 = TransactionalMail.objects.create(
            identifier='1', recipient='foo@bar', headers={'From': 'bar@foo'},
            sender='bar@foo', message=raw_mail_01, author=user)
        mail_02 = TransactionalMail.objects.create(
            identifier='2', recipient='bar@foo', headers={'From': 'foo@bar'},
            sender='foo@bar', message=raw_mail_02, author=user)

        purge_raw_mail()

        self.assertEqual(RawMail.objects.count(), 2)

        mail_01.message = None
        mail_01.save()

        purge_raw_mail()
        self.assertEqual(RawMail.objects.count(), 1)

        mail_03 = TransactionalMail.objects.create(
            identifier='3', recipient='bar@foo', headers={'From': 'foo@bar'},
            sender='foo@bar', message=raw_mail_02, author=user)

        mail_02.message = None
        mail_02.save()

        purge_raw_mail()
        self.assertEqual(RawMail.objects.count(), 1)
