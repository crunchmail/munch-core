from unittest.mock import patch

import django_fsm
from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from django.core.exceptions import ValidationError

from munch.core.utils.tests import temporary_settings
from munch.apps.spamcheck import SpamResult
from munch.apps.users.tests.factories import UserFactory
from munch.apps.spamcheck.tests import get_spam_result_mock

from ..exceptions import InvalidSubmitedData
from .factories import MessageFactory


@override_settings(SKIP_SPAM_CHECK=True, BYPASS_DNS_CHECKS=True)
class MessageTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)

    def test_empty_html(self):
        self.message.html = ' '
        with self.assertRaises(ValidationError):
            self.message.save()

    def test_add_messages_update_status(self):
        self.message.save()
        self.assertEqual(self.message.status, self.message.MSG_OK)

    def test_unauthorized_external_optout(self):
        self.assertEqual(
            self.message.author.organization.can_external_optout, False)
        self.message.external_optout = True

        with self.assertRaises(ValidationError):
            self.message.full_clean()
            self.message.save()

    def test_authorized_external_optout(self):
        self.message.author.organization.can_external_optout = True
        self.message.author.organization.save()

        self.message.external_optout = True
        self.message.full_clean()
        self.message.save()


@override_settings(SKIP_SPAM_CHECK=True)
class MessageStatesTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)

    def test_allowed_transition(self):
        """ NEW -> CANCELED"""
        self.message.status = self.message.MSG_ISSUES
        self.message.html = '<html>{}</html>'.format(
            settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.message.save()
        self.assertEqual(self.message.status, self.message.MSG_OK)

    def test_unallowed_transition(self):
        """NEW -> SENT"""
        self.message.status = self.message.SENT
        with self.assertRaises(django_fsm.TransitionNotAllowed):
            self.message.save()


@override_settings(SKIP_SPAM_CHECK=True)
class MessageTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)

    def test_plaintext_render(self):
        self.message.html = '<h1>Foubarr{}</h1>'.format(
            settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertIn('# Foubarr', self.message.mk_plaintext())

    def test_plaintext_render_keeps_accents(self):
        self.message.html = '<h1>é</h1>'
        self.assertIn('é', self.message.mk_plaintext())

    def test_css_inlining(self):
        self.message.html = (
            '<style>h1 {color: red}</style><h1>Foubarré</h1>%s') % (
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertIn('<h1 style="color:red">', self.message.mk_html())

    def test_css_inlining_keep_property_caps(self):
        self.message.html = (
            '<style>h1 {Margin: 1em}</style><h1>Foubarré</h1>%s') % (
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertIn('<h1 style="Margin:1em">', self.message.mk_html())

    def test_unsubscribe_link_preexisting(self):
        self.message.html = '<body><h1>Foubarr</h1><p>{}</p></body>'.format(
            settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertEqual(
            self.message.mk_html().count(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER']), 1)

    def test_clean_message_script(self):
        self.message.html = (
            '<head><script>alert("foo");</script>'
            '</head><body>{}</body>').format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertNotIn('<script>', self.message.mk_html())

    def test_clean_message_js(self):
        self.message.html = (
            '<head></head><body><h1 onclick="alert(\'foo\');">'
            '</h1>{}</body>').format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertNotIn('alert', self.message.mk_html())

    def test_detach_img(self):
        self.message.html = (
            '<img src="data:image/gif;base64'
            ',R0lGODdhAQABAIABAOvr6////ywAAAAAAQABAAACAkQBADs="/>{}').format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertIn('/uploads/images/', self.message.mk_html())

    def test_retain_body_attributes(self):
        self.message.html = (
            '<body style="width: 100%"><h1>A</h1><p>B</p>{}</body>').format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertIn('style="width: 100%"', self.message.mk_html())

    def test_do_not_div_wrap_document(self):
        """
        see bug #1542
        """
        self.message.html = (
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
            '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
            '<html xmlns="http://www.w3.org/1999/xhtml">'
            '<body leftmargin="0" marginwidth="0" topmargin="0" '
            'marginheight="0" offset="0">{}</body></html>').format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertNotIn('<div>', self.message.mk_html())

    def test_preserve_doctype(self):
        self.message.html = (
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
            '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
            '<html xmlns="http://www.w3.org/1999/xhtml">{}</html>').format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertIn((
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0'
            ' Transitional//EN" "http://www.w3.org/TR/'
            'xhtml1/DTD/xhtml1-transitional.dtd">').format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER']),
            self.message.mk_html())
        self.assertIn(
            'xmlns="http://www.w3.org/1999/xhtml', self.message.mk_html())

    def test_strip_comments(self):
        self.message.html = '<body><!-- IM COMMENT -->{}</body>'.format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertNotIn('COMMENT', self.message.mk_html())

    def test_preserve_conditional_comments(self):
        self.message.html = (
            "<body><!--[if IE 6]><p>MARK</p><![endif]-->{}</body>").format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertIn('MARK', self.message.mk_html())

    def test_remove_tbody(self):
        """Checks that <tbody> are removed but their contents remains """
        self.message.html = (
            "<body><table><tbody><tr><td>PLACEHOLDER</td>"
            "</tr></tbody></table>{}</body>").format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertNotIn('<tbody>', self.message.mk_html())
        self.assertIn('<tr><td>PLACEHOLDER</td></tr>', self.message.mk_html())

    def test_remove_link(self):
        self.message.html = (
            '<head><link rel="home" href="/" /></head><body>{}</body>').format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertNotIn('<link', self.message.mk_html())

    def test_fetch_img(self):
        self.message.detach_images = True
        self.message.html = (
            '<img src="http://www.oasiswork.fr/uploads'
            '/logo_oasiswork.jpg" />{}').format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        html = self.message.mk_html()
        self.assertIn('/uploads/images/', html)
        self.assertNotIn('src="http://www.oasiswork.fr', html)

    def test_do_not_fetch_img(self):
        self.message.detach_images = False
        self.message.html = (
            '<img src="http://www.oasiswork.fr/uploads'
            '/logo_oasiswork.jpg" />{}').format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        self.assertIn(
            'src="http://www.oasiswork.fr/uploads/logo_oasiswork.jpg"',
            self.message.mk_html())

    def test_invalid_html(self):
        """ Invalid because of missing src attr
        """
        with self.assertRaises(InvalidSubmitedData):
            self.message.html = '<img'
            self.message.mk_html()

    def test_spam_check(self):
        self.message.html = '<body><h1>Foubarr</h1> {}</body>'.format(
            settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])

        with patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=get_spam_result_mock):
            check_res = self.message.spam_check()
        self.assertIsInstance(check_res, SpamResult)
