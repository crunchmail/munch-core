import re
import unittest

from django.core import mail
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.test import TestCase
from django.test.utils import override_settings

from ..models import MunchUser
from ..models import Organization

from .factories import UserFactory


class OrganizationTests(TestCase):
    def test_settings_auto_created(self):
        c = Organization(name='Test', contact_email='test@example.com')
        c.save()
        self.assertTrue(c.settings)


@override_settings(
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_ALWAYS_EAGER=True, BROKER_BACKEND='memory')
class OrganizationSettingsTests(TestCase):
    def test_external_optout_create(self):
        c = Organization(
            name='Test', can_external_optout=True,
            contact_email='test@example.com')
        c.save()
        c.settings.external_optout_message = 'Jean-Jack : 01.01.01.01.01'
        c.settings.save()
        self.assertEqual(c.name, 'Test')
        self.assertEqual(
            c.settings.external_optout_message, 'Jean-Jack : 01.01.01.01.01')

    def test_external_optout_message_not_allowed(self):
        with self.assertRaises(ValidationError):
            c = Organization(
                name='Test', can_external_optout=False,
                contact_email='test@example.com')
            c.save()
            c.settings.external_optout_message = 'Jean-Jack : 01.01.01.01.01'
            c.settings.full_clean()
            c.settings.save()


class TestSecret(TestCase):
    def test_key_generation(self):
        s1 = MunchUser._mk_random_secret()
        self.assertEqual(len(s1), MunchUser.SECRET_LENGTH)

    def test_key_differs(self):
        s1 = MunchUser._mk_random_secret()
        s2 = MunchUser._mk_random_secret()
        self.assertNotEqual(s1, s2)

    def test_create_user_gens_secret(self):
        c = Organization.objects.filter(pk=1024).first()
        u = MunchUser.objects.create(
            identifier='foo@bar.example.com', organization=c,
            last_login=timezone.now())
        self.assertEqual(len(u.secret), MunchUser.SECRET_LENGTH)


@override_settings(
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_ALWAYS_EAGER=True, BROKER_BACKEND='memory')
class TestMunchUser(TestCase):
    @unittest.skip('Must check if email backend successfully send email')
    def test_create_user(self):
        user = UserFactory(
            identifier='foo@example.com', last_login=timezone.now())
        self.assertEqual(user.identifier, 'foo@example.com')
        # account activation email
        self.assertEqual(len(mail.outbox), 0)


@override_settings(OPTOUTS_ADDRESS='http://testserver')
class TestPasswordReset(TestCase):
    @unittest.skip('Must check if email backend successfully send email')
    def test_password_reset(self):
        user = MunchUser.objects.create(
            is_active=True, is_admin=False)

        user.send_password_reset_email()
        reset_link = re.compile(r'http://.*reset/.*/')
        matches = reset_link.findall(mail.outbox[0].body)
        self.assertEqual(len(matches), 1)
        reset_url = matches[0]
        response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<form', response.content)

        # form submit
        response = self.client.post(reset_url, {
            'new_password1': 'imnew', 'new_password2': 'imnew'})
        self.assertEqual(response.status_code, 302)
        response = self.client.get(response['Location'])

        self.assertEqual(response.status_code, 200)

        login_ok = self.client.login(
            identifier=user.identifier, password='imnew')
        self.assertTrue(login_ok)
