from datetime import datetime
from email.utils import format_datetime

import pytz
import factory.django
from faker import Factory as FakerFactory

from munch.core.mail.models import RawMail
from munch.apps.users.tests.factories import UserFactory

from ..models import Mail
from ..models import get_mail_identifier

faker = FakerFactory.create()


class MailFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Mail

    identifier = factory.LazyAttribute(lambda x: get_mail_identifier())
    creation_date = factory.LazyAttribute(lambda x: datetime.now(pytz.UTC))
    headers = factory.LazyAttribute(lambda x: {
        'To': faker.email(), 'Date': format_datetime(datetime.now(pytz.UTC))})
    message = factory.LazyAttribute(
        lambda x: RawMail.objects.create(content='Test'))
    author = factory.SubFactory(UserFactory)
