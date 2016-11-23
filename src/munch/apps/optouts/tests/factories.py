import factory.django
from faker import Factory as FakerFactory

from ..models import OptOut

faker = FakerFactory.create()


class OptOutFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OptOut

    origin = OptOut.BY_MAIL
    address = factory.LazyAttribute(lambda x: faker.email())
