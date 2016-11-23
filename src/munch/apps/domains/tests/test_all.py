from datetime import datetime
from unittest.mock import patch
from unittest.mock import MagicMock

import dns
import pytz
from django.test import TestCase
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test.utils import override_settings
from libfaketime import fake_time

from munch.apps.users.tests.factories import UserFactory
from munch.apps.campaigns.tests.factories import MessageFactory

from ..utils import SPFValidator
from ..models import SendingDomain
from ..fields import DomainCheckField
from ..tasks import run_domains_validation
from ..tasks import validate_sending_domain_field

from .factories import SendingDomainFactory


def DNSResultMock(v):
    """ Mocks DNS, single valued response

    DNSResultMock(42)
    DNSResultMock[1].to_text()
    """
    m = MagicMock()
    sub_mock = MagicMock()
    sub_mock.to_text.return_value = v
    m.__getitem__.return_value = sub_mock
    m.__iter__.return_value = [sub_mock]
    return m


def DNSEmptyEntryMock():
    m = MagicMock()
    m.__getitem__.side_effect = IndexError()
    return m


def mock_resolver(queries):
    mock_queries = queries

    def mock_resolve(name, field):
        try:
            res = mock_queries[name][field]
        except KeyError:
            raise dns.exception.DNSException
        else:
            if getattr(res, 'side_effect', None):
                # Raise exception if needed
                return res()
            else:
                return res
    m = MagicMock()
    m.side_effect = mock_resolve
    return m

mock_queries = {
    'test._domainkey.sandbox.munch.example.com': {
        'TXT': DNSResultMock(settings.DOMAINS['DKIM_KEY_CONTENT'])},
    'sandbox.munch.example.com': {
        'TXT': DNSResultMock('"v=spf1 include:spf.munch.example.com -all"')},  # noqa
    'test._domainkey.bad.sandbox.munch.example.com': {
        'TXT': DNSResultMock(settings.DOMAINS[
            'DKIM_KEY_CONTENT'].replace('1', '2'))},
    'bad.sandbox.munch.example.com': {
        'TXT': DNSResultMock('"v=spf1 redirect=_spf.google.com ~all"')}
}


class DNSCheckTestCase(TestCase):
    ok_domain = 'sandbox.munch.example.com'
    bad_domain = 'bad.sandbox.munch.example.com'
    inexistant_domain = 'donotexist.munch.example.com'

    def setUp(self):
        settings.DOMAINS['DKIM_KEY_ID'] = 'test'

        self.user_1 = UserFactory()
        self.user_2 = UserFactory()

        self.resolver = mock_resolver(mock_queries)
        with fake_time('2099-10-10 06:00:00'):
            with patch('dns.resolver.query', self.resolver):
                SendingDomainFactory(
                    organization=self.user_1.organization, name=self.ok_domain)
                SendingDomainFactory(
                    organization=self.user_1.organization,
                    name=self.bad_domain)
                SendingDomainFactory(
                    organization=self.user_1.organization,
                    name=self.inexistant_domain)
                SendingDomainFactory(
                    organization=self.user_2.organization, name='example.com')
                SendingDomainFactory(
                    organization=self.user_2.organization,
                    name='gentle.example.com')


@override_settings(BYPASS_DNS_CHECKS=False)
class SendingDomainDKIMTestCase(DNSCheckTestCase):
    def test_valid_domain(self):
        dom = SendingDomain.objects.get(name=self.ok_domain)
        with patch('dns.resolver.query', self.resolver):
            dom.validate_dkim()
            self.assertEqual(dom.dkim_status, DomainCheckField.OK)

    def test_inexistant_domain(self):
        dom = SendingDomain.objects.get(name=self.inexistant_domain)
        with patch('dns.resolver.query', self.resolver):
            dom.validate_dkim()
            self.assertEqual(dom.dkim_status, DomainCheckField.NOT_CONFIGURED)

    def test_invalid_domain(self):
        dom = SendingDomain.objects.get(name=self.bad_domain)
        with patch('dns.resolver.query', self.resolver):
            dom.validate_dkim()
            self.assertEqual(
                dom.dkim_status, DomainCheckField.BADLY_CONFIGURED)


@override_settings(BYPASS_DNS_CHECKS=True)
class DomainSyntaxValidation(DNSCheckTestCase):
    def test_invalid_domain(self):
        sd = SendingDomain(
            name='notadomainright', organization=self.user_2.organization)
        with self.assertRaises(ValidationError):
            sd.full_clean()

    def test_valid_domain(self):
        sd = SendingDomain(
            name='example.com', organization=self.user_2.organization)
        with self.assertRaises(ValidationError):
            sd.full_clean()


@override_settings(BYPASS_DNS_CHECKS=False)
class EnvelopeDomainValidation(DNSCheckTestCase):
    def setUp(self):
        super().setUp()
        self.v = SPFValidator(spf_include='spf.munch.example.com')

    def test_valid_domain(self):
        with patch('dns.resolver.query', self.resolver):
            self.v.validate(self.ok_domain)

    def test_inexistant_domain(self):
        with patch('dns.resolver.query', self.resolver):
            with self.assertRaisesRegexp(ValidationError, 'not configured'):
                self.v.validate(self.inexistant_domain)

    def test_invalid_domain(self):
        with patch('dns.resolver.query', self.resolver):
            with self.assertRaisesRegexp(
                    ValidationError, 'badly configured'):
                self.v.validate(self.bad_domain)


@override_settings(
    BYPASS_DNS_CHECKS=False, RETURNPATH_DOMAIN='sandbox.munch.example.com')
class SenderEmailValidation(DNSCheckTestCase):
    def setUp(self):
        super().setUp()
        settings.DOMAINS['SPF_INCLUDE'] = 'spf.munch.example.com'

    def _mk_message(self, sender):
        return MessageFactory(sender_email=sender, author=self.user_1)

    def test_savable_message(self):
        with patch('dns.resolver.query', self.resolver):
            self._mk_message('test@' + self.ok_domain)

    def test_unsavable_message_invalid_domain(self):
        with patch('dns.resolver.query', self.resolver):
            with self.assertRaises(ValidationError):
                self._mk_message('test@' + self.bad_domain)

    def test_unsavable_message_unregistered_domain(self):
        SendingDomain.objects.all().delete()
        with patch('dns.resolver.query', self.resolver):
            with self.assertRaises(ValidationError):
                self._mk_message('test@' + self.ok_domain)


@override_settings(BYPASS_DNS_CHECKS=False)
class SendingDomainTaskTestCase(DNSCheckTestCase):
    def test_untouch_domains(self):
        self.assertEqual(
            SendingDomain.objects.get(
                name='sandbox.munch.example.com').dkim_status,
            DomainCheckField.OK)
        self.assertEqual(
            SendingDomain.objects.get(
                name='bad.sandbox.munch.example.com').dkim_status,
            DomainCheckField.BADLY_CONFIGURED)
        self.assertEqual(
            SendingDomain.objects.get(
                name='donotexist.munch.example.com').dkim_status,
            DomainCheckField.NOT_CONFIGURED)

        with patch('dns.resolver.query', self.resolver):
            run_domains_validation([
                DomainCheckField.OK, DomainCheckField.NOT_CONFIGURED,
                DomainCheckField.BADLY_CONFIGURED, DomainCheckField.PENDING,
                DomainCheckField.UNKNOWN])

        self.assertEqual(
            SendingDomain.objects.get(
                name='sandbox.munch.example.com').dkim_status,
            DomainCheckField.OK)
        self.assertEqual(
            SendingDomain.objects.get(
                name='bad.sandbox.munch.example.com').dkim_status,
            DomainCheckField.BADLY_CONFIGURED)
        self.assertEqual(
            SendingDomain.objects.get(
                name='donotexist.munch.example.com').dkim_status,
            DomainCheckField.NOT_CONFIGURED)

    def test_bad_to_well(self):
        mock_queries = {
            'test._domainkey.bad.sandbox.munch.example.com': {
                'TXT': DNSResultMock(settings.DOMAINS['DKIM_KEY_CONTENT'])}
        }
        resolver = mock_resolver(mock_queries)
        with patch('dns.resolver.query', resolver):
            run_domains_validation([DomainCheckField.BADLY_CONFIGURED])

        self.assertEqual(
            SendingDomain.objects.get(
                name='bad.sandbox.munch.example.com').dkim_status,
            DomainCheckField.OK)

    def test_update_dkim_status_date(self):
        mock_queries = {
            'test._domainkey.bad.sandbox.munch.example.com': {
                'TXT': DNSResultMock(settings.DOMAINS['DKIM_KEY_CONTENT'])}
        }
        resolver = mock_resolver(mock_queries)

        domain = SendingDomain.objects.get(
            name='bad.sandbox.munch.example.com')

        with fake_time('2099-10-10 08:00:00'):
            with patch('dns.resolver.query', resolver):
                validate_sending_domain_field(domain.id, 'dkim')

        self.assertEqual(SendingDomain.objects.get(
            name='bad.sandbox.munch.example.com').dkim_status_date,
            datetime(year=2099, month=10, day=10, hour=6).replace(
                tzinfo=pytz.UTC))
        self.assertEqual(
            SendingDomain.objects.get(
                name='bad.sandbox.munch.example.com').dkim_status,
            DomainCheckField.OK)

    def test_ignore_old_dkim_status_change_when_bad(self):
        """
        'run_domains_validation' task must ignore
        domains that failed since more than 2 days.
        In order to prevent checking a badly configured
        domain during a long time.
        """
        mock_queries = {
            'test._domainkey.bad.sandbox.munch.example.com': {
                'TXT': DNSResultMock(settings.DOMAINS['DKIM_KEY_CONTENT'])}
        }
        resolver = mock_resolver(mock_queries)

        # Must be OK with "resolver"
        with fake_time('2099-10-12 08:00:00'):
            with patch('dns.resolver.query', resolver):
                run_domains_validation([DomainCheckField.BADLY_CONFIGURED])

        self.assertEqual(SendingDomain.objects.get(
            name='bad.sandbox.munch.example.com').dkim_status,
            DomainCheckField.BADLY_CONFIGURED)
        self.assertEqual(SendingDomain.objects.get(
            name='bad.sandbox.munch.example.com').dkim_status_date,
            datetime(year=2099, month=10, day=10, hour=4).replace(
                tzinfo=pytz.UTC))

    def test_do_not_ignore_dkim_status_change_when_ok(self):
        """
        'run_domains_validation' task wont ignore status change for domains
        that were 'OK'. In order to always check 'OK' domains for a long time
        """
        mock_queries = {
            'test._domainkey.bad.sandbox.munch.example.com': {
                'TXT': DNSResultMock(settings.DOMAINS['DKIM_KEY_CONTENT'])}
        }
        resolver = mock_resolver(mock_queries)

        # Must be OK with "resolver"
        with fake_time('2099-10-10 08:00:00'):
            with patch('dns.resolver.query', resolver):
                run_domains_validation([DomainCheckField.BADLY_CONFIGURED])

        self.assertEqual(SendingDomain.objects.get(
            name='bad.sandbox.munch.example.com').dkim_status,
            DomainCheckField.OK)

        # Must fail with "self.resolver"
        with fake_time('2100-10-10 08:00:00'):
            with patch('dns.resolver.query', self.resolver):
                run_domains_validation([DomainCheckField.OK])

        self.assertEqual(SendingDomain.objects.get(
            name='bad.sandbox.munch.example.com').dkim_status,
            DomainCheckField.BADLY_CONFIGURED)
        self.assertEqual(SendingDomain.objects.get(
            name='bad.sandbox.munch.example.com').dkim_status_date,
            datetime(year=2100, month=10, day=10, hour=6).replace(
                tzinfo=pytz.UTC))
