from datetime import datetime

import pytz
import factory.django
from django.conf import settings
from faker import Factory as FakerFactory

from munch.core.mail.utils import mk_base64_uuid
from munch.apps.domains.models import SendingDomain

from ..models import Mail
from ..models import Message
from ..models import MailStatus
from ..models import PreviewMail
from ..models import get_base_mail_identifier

faker = FakerFactory.create()


class MessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Message

    class Params:
        html_content = '{} {}'.format(
            settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'],
            settings.HOSTED['WEB_LINK_PLACEHOLDER'])

    name = factory.LazyAttribute(lambda x: faker.sentence(nb_words=3))
    creation_date = factory.LazyAttribute(lambda x: datetime.now(pytz.UTC))
    sender_email = factory.LazyAttribute(lambda x: faker.email())
    sender_name = factory.LazyAttribute(lambda x: faker.name())
    identifier = factory.LazyAttribute(lambda x: mk_base64_uuid())
    html = factory.LazyAttribute(lambda o: '<body>{} {}</body>'.format(
        o.html_content, faker.text(max_nb_chars=100)))

    @factory.post_generation
    def auto_create_sending_domain(
            self, create, extracted, create_sending_domain=True):
        if not create:
            return

        if create_sending_domain:
            SendingDomain.objects.create(
                name=self.name, organization=self.author.organization)


class MailFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Mail

    message = factory.SubFactory(MessageFactory)
    curstatus = 'unknown'
    creation_date = factory.LazyAttribute(lambda x: datetime.now(pytz.UTC))
    identifier = factory.LazyAttribute(lambda x: get_base_mail_identifier())
    recipient = factory.LazyAttribute(lambda x: faker.email())


class MailStatusFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MailStatus

    creation_date = factory.LazyAttribute(lambda x: datetime.now(pytz.UTC))


class PreviewMailFactory(MailFactory):
    class Meta:
        model = PreviewMail
