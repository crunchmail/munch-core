from unittest import TestCase
from unittest.mock import patch
from unittest.mock import MagicMock
from urllib.parse import urlparse

import dns
from django.conf import settings

from munch.core.mail.utils import get_app_url
from munch.apps.domains.fields import DomainCheckField
from munch.apps.users.tests.factories import OrganizationFactory

from ..models import SendingDomain
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
                return res()  # raise exception if needed
            else:
                return res
    m = MagicMock()
    m.side_effect = mock_resolve
    return m

APP_DOMAIN_CNAME = 'c.munch.local'
ok_app_domain = 'app.good.example.com'
bad_app_domain = 'app.bad.example.com'
notconfigured_app_domain = 'app.notconfigured.example.com'
inexistant_app_domain = 'donotexist.example.com'

mock_queries = {
    ok_app_domain: {
        'CNAME': DNSResultMock('{}.'.format(APP_DOMAIN_CNAME))},
    bad_app_domain: {'CNAME': DNSResultMock(
        'another.domain.com.')},
    notconfigured_app_domain: {'CNAME': DNSEmptyEntryMock()}}


class SendingDomainAppDomainTestCase(TestCase):
    def setUp(self):
        self.resolver = mock_resolver(mock_queries)
        settings.USERS['ORGANIZATION_APP_DOMAIN_CNAME'] = APP_DOMAIN_CNAME

    def test_app_domain_validate_ok(self):
        with patch('dns.resolver.query', self.resolver):
            domain = SendingDomainFactory(app_domain=ok_app_domain)
            domain.validate_app_domain()
            self.assertEqual(domain.app_domain_status, DomainCheckField.OK)

    def test_app_domain_validate_bad(self):
        with patch('dns.resolver.query', self.resolver):
            domain = SendingDomainFactory(app_domain=bad_app_domain)
            domain.validate_app_domain()
            self.assertEqual(
                domain.app_domain_status, DomainCheckField.BADLY_CONFIGURED)

    def test_app_domain_validate_notconfigured(self):
        with patch('dns.resolver.query', self.resolver):
            domain = SendingDomainFactory(app_domain=notconfigured_app_domain)
            domain.validate_app_domain()
            self.assertEqual(
                domain.app_domain_status, DomainCheckField.NOT_CONFIGURED)

    def test_app_domain_validate_inexistant(self):
        with patch('dns.resolver.query', self.resolver):
            domain = SendingDomainFactory(app_domain=inexistant_app_domain)
            domain.validate_app_domain()
            self.assertEqual(
                domain.app_domain_status, DomainCheckField.NOT_CONFIGURED)

    def test_get_app_url_default(self):
        org = OrganizationFactory()
        domain = SendingDomainFactory(organization=org)
        url = get_app_url(domain=domain, organization=org)
        self.assertEqual(url, settings.APPLICATION_URL)

    def test_get_app_url_good(self):
        with patch('dns.resolver.query', self.resolver):
            org = OrganizationFactory()
            domain = SendingDomainFactory(
                app_domain=ok_app_domain, organization=org)

            # retrieve object from DB to get latest app_domain_status
            domain = SendingDomain.objects.get(pk=domain.pk)

            url = get_app_url(domain=domain, organization=org)
            def_u = urlparse(settings.APPLICATION_URL.strip('/'))
            app_u = '{}://{}'.format(def_u.scheme, ok_app_domain)
            if def_u.port:
                app_u += ':{}'.format(def_u.port)
            self.assertEqual(url, app_u)

    def test_get_app_url_bad(self):
        with patch('dns.resolver.query', self.resolver):
            org = OrganizationFactory()
            domain = SendingDomainFactory(
                app_domain=bad_app_domain, organization=org)
            url = get_app_url(domain=domain, organization=org)
            self.assertEqual(url, settings.APPLICATION_URL)
