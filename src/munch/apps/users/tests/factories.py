import factory
import factory.django
from django.utils import timezone
from django.contrib.auth.models import Group
from faker import Factory as FakerFactory

from munch.core.mail.utils import mk_base64_uuid

from ..models import MunchUser
from ..models import Organization
from ..models import APIApplication
from ..models import SmtpApplication


faker = FakerFactory.create()


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.LazyAttribute(lambda x: faker.sentence(nb_words=3))
    contact_email = factory.LazyAttribute(lambda x: faker.email())


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MunchUser

    organization = factory.SubFactory(OrganizationFactory)
    identifier = factory.LazyAttribute(lambda x: faker.email())
    last_login = factory.LazyAttribute(lambda x: timezone.now())
    secret = factory.LazyAttribute(lambda x: mk_base64_uuid())
    is_active = True
    password = factory.PostGenerationMethodCall('set_password', 'password')

    @factory.post_generation
    def groups(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for group in extracted:
                if group in [
                        'users', 'collaborators',
                        'managers', 'administrators']:
                    self.groups.add(Group.objects.filter(name=group)[0])


class SmtpApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SmtpApplication

    identifier = factory.LazyAttribute(lambda x: faker.sentence(nb_words=2))
    author = factory.SubFactory(UserFactory)


class APIApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = APIApplication

    identifier = factory.LazyAttribute(lambda x: faker.sentence(nb_words=2))
    author = factory.SubFactory(UserFactory)
