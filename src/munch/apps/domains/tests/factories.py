import factory.django
from faker import Factory as FakerFactory

from munch.apps.users.tests.factories import OrganizationFactory

from ..models import SendingDomain

faker = FakerFactory.create()


class SendingDomainFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SendingDomain

    name = factory.LazyAttribute(lambda x: faker.domain_name())
    organization = factory.SubFactory(OrganizationFactory)
