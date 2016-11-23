from django.test import TestCase

from munch.core.tests.factories import CategoryFactory
from munch.apps.users.tests.factories import UserFactory
from munch.apps.optouts.tests.factories import OptOutFactory

from ..models import OptOut
from .factories import MailFactory
from .factories import MessageFactory


class OptOuts(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_optout_no_send(self):
        """
        Check that previous optouts from same
        category are honored in current category.
        """
        # A prev_message, in same category, with an optout
        category = CategoryFactory(author=self.user)
        old_message = MessageFactory(author=self.user, category=category)
        dark_mail = MailFactory(message=old_message)
        OptOutFactory(
            author=dark_mail.message.author,
            category=dark_mail.message.category,
            identifier=dark_mail.identifier,
            address=dark_mail.recipient,
            origin=OptOut.BY_WEB)

        # A message, in same category
        new_message = MessageFactory(author=self.user, category=category)
        MailFactory(message=new_message, recipient=dark_mail.recipient)
        good_mail = MailFactory(message=new_message)

        self.assertEqual(
            list(new_message.willsend_addresses()), [good_mail.recipient])
        self.assertEqual(
            list(new_message.willnotsend_addresses()),
            [dark_mail.recipient])

    def test_optout_send(self):
        """
        Check that previous optouts from different
        category are ignored in current category.
        """
        # A prev_message, in different category, with an optout
        old_category = CategoryFactory(author=self.user)
        old_message = MessageFactory(author=self.user, category=old_category)
        dark_mail = MailFactory(message=old_message)
        OptOutFactory(
            author=dark_mail.message.author,
            category=dark_mail.message.category,
            identifier=dark_mail.identifier,
            address=dark_mail.recipient,
            origin=OptOut.BY_WEB)

        # A message, in same category
        new_category = CategoryFactory(author=self.user)
        new_message = MessageFactory(author=self.user, category=new_category)
        MailFactory(message=new_message, recipient=dark_mail.recipient)
        good_mail = MailFactory(message=new_message)

        self.assertEqual(
            set(list(new_message.willsend_addresses())),
            set([dark_mail.recipient, good_mail.recipient]))
        self.assertEqual(list(new_message.willnotsend_addresses()), [])

    def test_optout_count(self):
        category = CategoryFactory(author=self.user)
        message = MessageFactory(author=self.user, category=category)

        cases = [
            ('1@example.com', OptOut.BY_WEB),
            ('2@example.com', OptOut.BY_FBL),
            ('4@example.com', OptOut.BY_BOUNCE),
            ('3@example.com', OptOut.BY_ABUSE),
            ('5@example.com', OptOut.BY_ABUSE)]
        for addr, origin in cases:
            mail = MailFactory(message=message, recipient=addr)
            OptOutFactory(
                identifier=mail.identifier,
                address=mail.recipient,
                origin=origin)

        res = OptOut.objects.count_by_origin()
        self.assertEqual(
            res,
            {'mail': 0, 'abuse': 2, 'feedback-loop': 1, 'bounce': 1, 'web': 1})
