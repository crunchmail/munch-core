import unittest
import datetime

import pytz
from django.test import TestCase

from ..mail.utils import parse_email_date
from ..mail.utils import UniqueEmailAddressParser
from ..utils.permissions import MunchResourcePermission


class PermissionsTestCase(TestCase):
    def test_munch_resource_permission_names(self):
        self.assertEqual(
            MunchResourcePermission().mk_perms(verb='change'),
            (
                'campaigns.change_mine_mail',
                'campaigns.change_organizations_mail',
                'campaigns.change_mail'))



class TestMunchAddress(unittest.TestCase):
    def setUp(self):
        self.RPAddressParser = UniqueEmailAddressParser(
            domain='example.com', prefix='return-')

        self.UnsubscribeAddressParser = UniqueEmailAddressParser(
            domain='example.com', prefix='unsubscribe-')

    def test_valid_addr(self):
        s = 'return-fH7eGy3qQLuLGgr13RfJoA@example.com'
        self.assertTrue(
            self.RPAddressParser.is_valid(s))
        self.assertFalse(
            self.UnsubscribeAddressParser.is_valid(s))

    def test_invalid_addr(self):
        self.assertFalse(self.RPAddressParser.is_valid(
            'invalid+fH7eGy3qQLuLGgr13RfJoA@example.com'))

        self.assertFalse(self.RPAddressParser.is_valid(
            'return+fH7eGy3qQLuLGgr13RfJoA@invalid.example.com'))

    def test_creation(self):
        self.assertTrue(self.RPAddressParser.new())

    def test_creation_uuid_provided(self):
        ma = self.RPAddressParser.new('fH7eGy3qQLuLGgr13RfJoA')
        self.assertTrue(self.RPAddressParser.is_valid(ma))
        self.assertEqual(ma, 'return-fH7eGy3qQLuLGgr13RfJoA@example.com')

    def test_uuid_extraction(self):
        self.assertEqual(
            self.RPAddressParser.get_uuid(
                'return-fH7eGy3qQLuLGgr13RfJoA@example.com'),
            'fH7eGy3qQLuLGgr13RfJoA')

    def test_multiple_address_parser(self):
        RPAddressParser_1 = UniqueEmailAddressParser(
            domain='example_1', prefix='prefix_1')
        RPAddressParser_2 = UniqueEmailAddressParser(
            domain='example_2', prefix='prefix_2')

        self.assertNotEqual(RPAddressParser_1, RPAddressParser_2)
        self.assertNotEqual(RPAddressParser_1.domain, RPAddressParser_2.domain)
        self.assertNotEqual(RPAddressParser_1.prefix, RPAddressParser_2.prefix)


class TestUtils(unittest.TestCase):
    def test_parse_email_date(self):
        d = parse_email_date('Sat, 24 Nov 2035 11:45:15 -0500')
        self.assertEqual(
            pytz.utc.localize(datetime.datetime(
                year=2035, month=11, day=24, hour=16, minute=45, second=15)),
            d)
