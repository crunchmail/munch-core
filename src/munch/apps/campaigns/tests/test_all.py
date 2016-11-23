from django.test import TestCase

from munch.apps.users.tests.factories import UserFactory
from munch.apps.optouts.tests.factories import OptOutFactory

from .factories import MailFactory
from .factories import MessageFactory


class AllModelsTests(TestCase):
    def test_get_organization(self):
        """
        Check that all the category app define a get_organization() method
        """
        user = UserFactory()
        message = MessageFactory(author=user)
        mail = MailFactory(message=message)
        optout = OptOutFactory(
            author=user, category=message.category,
            identifier=mail.identifier, address=mail.recipient)
        klasses = [
            user.organization, message, mail.statuses.first(), mail, optout]

        for obj in klasses:
            self.assertEqual(obj.get_organization().pk, user.organization.pk)
