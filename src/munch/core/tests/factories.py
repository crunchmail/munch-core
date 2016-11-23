import factory.django
from faker import Factory as FakerFactory

from ..models import Category

faker = FakerFactory.create()


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.LazyAttribute(lambda x: faker.word())
