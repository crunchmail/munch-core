import logging

from unittest.mock import patch
from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from libfaketime import fake_time

from munch.apps.campaigns.models import Mail
from munch.apps.campaigns.models import MailStatus
from munch.apps.campaigns.tests.factories import MailFactory
from munch.apps.campaigns.tests.factories import MessageFactory
from munch.apps.campaigns.tests.factories import MailStatusFactory
from munch.apps.users.tests.factories import UserFactory

from munch.apps.spamcheck.tests import get_spam_result_mock

from .utils import WebKey
from .views import TRACKER_PIXEL
from .models import LinkMap
from .models import TrackRecord
from .models import READ_BROWSER
from .models import READ_MUA_PIXEL

from .contentfilters import LinksRewriter
from .contentfilters import WebVersionLinksRewriter
from .contentfilters import rewrite_plaintext_links


logging.disable(logging.CRITICAL)


class TestTrackingPixel(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_valid_tracker(self):
        with fake_time('2016-10-10 08:00:00'):
            message = MessageFactory(status='message_ok', author=self.user)
            mail = MailFactory(message=message)
            MailStatusFactory(mail=mail)
            MailStatusFactory(mail=mail, status=MailStatus.SENDING)
            MailStatusFactory(mail=mail, status=MailStatus.DELIVERED)
        with fake_time('2016-10-10 08:00:15'):
            resp = self.client.get('/t/open/{}'.format(mail.identifier))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'image/gif')
        self.assertEqual(resp.content, TRACKER_PIXEL)

        records = TrackRecord.objects.filter(
            identifier=mail.identifier,
            kind='read', properties__source=READ_MUA_PIXEL)

        self.assertEqual(records.count(), 1)

    def test_unfilled_tracker(self):
        resp = self.client.get('/t/open/')
        self.assertEqual(resp.status_code, 404)

    def test_invalid_tracker(self):
        resp = self.client.get('/t/open/4242')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'image/gif')
        self.assertEqual(resp.content, TRACKER_PIXEL)

    def test_invalid_method(self):
        message = MessageFactory(status='message_ok', author=self.user)
        resp = self.client.post('/t/open/{}'.format(message.identifier))
        self.assertEqual(resp.status_code, 405)

    def test_reaction_time(self):
        with fake_time('2016-10-10 08:00:00'):
            message = MessageFactory(status='message_ok', author=self.user)
            mail = MailFactory(message=message)
            MailStatusFactory(mail=mail)
            MailStatusFactory(mail=mail, status=MailStatus.SENDING)
            MailStatusFactory(mail=mail, status=MailStatus.DELIVERED)
        with fake_time('2016-10-10 08:00:15'):
            self.client.get('/t/open/{}'.format(mail.identifier))
            records = TrackRecord.objects.filter(
                identifier=mail.identifier, kind='read')

        self.assertEqual(records.first().properties['reaction_time'], '15')

    def test_html_generation(self):
        message = MessageFactory(
            author=self.user,
            track_open=True, html='<body><h1>Foo</h1>{}</body>'.format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER']))
        mail = MailFactory(message=message)

        with patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=get_spam_result_mock):
            message.save()

        content = message.to_mail(mail)
        self.assertIn('t/open/', content.alternatives[0][0])

    def test_html_non_generation(self):
        message = MessageFactory(
            author=self.user,
            track_open=False, html='<body><h1>Foo</h1>{}</body>'.format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER']))
        with patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=get_spam_result_mock):
            message.save()

        mail = MailFactory(message=message)
        content = message.to_mail(mail)
        self.assertNotIn('pixel.gif', content.alternatives[0][0])

    def test_html_generation_preserve_doctype(self):
        message = MessageFactory(
            author=self.user, track_open=True, html=(
                '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//E'
                'N" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
                '<html xmlns="http://www.w3.org/1999/xhtml">{}</html>').format(
                    settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER']))

        with patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=get_spam_result_mock):
            message.save()

        mail = MailFactory(message=message)
        content = message.to_mail(mail)
        self.assertIn(
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
            '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">',
            content.alternatives[0][0])


class TestWebTracking(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)

    def test_hosted_mail_nokey_notrack(self):
        self.client.get('/archive/{}/'.format(self.message.identifier))
        self.assertEqual(TrackRecord.objects.filter(kind='read').count(), 0)

    def test_hosted_mail_badkey_notrack(self):
        self.client.get('/archive/{}/?web_key=1234'.format(
            self.message.identifier))
        self.assertEqual(TrackRecord.objects.filter(kind='read').count(), 0)

    def test_hosted_mail_with_key_works_tracks(self):
        mail = MailFactory(message=self.message)
        MailStatusFactory(mail=mail, status=MailStatus.QUEUED)
        MailStatusFactory(mail=mail, status=MailStatus.SENDING)
        MailStatusFactory(mail=mail, status=MailStatus.DELIVERED)

        wk = WebKey.from_instance(Mail.objects.first().identifier)
        response = self.client.get('/archive/{}/?web_key={}'.format(
            self.message.identifier, wk.token))
        self.assertEqual(response.status_code, 200)

        record = TrackRecord.objects.filter(kind='read').first()
        self.assertEqual(TrackRecord.objects.filter(kind='read').count(), 1)
        self.assertEqual(record.properties['source'], READ_BROWSER)


class TestTrackingLinks(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(
            author=self.user, track_clicks=True, track_open=False,
            html=(
                '<body><a href="http://example.com">'
                'Hi</a>{}</body>').format(
                    settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER']))
        with patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=get_spam_result_mock):
            self.message.save()
        self.mail = MailFactory(message=self.message)

    def test_html_generation(self):
        with patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=get_spam_result_mock):
            self.message.save()
        content = self.message.to_mail(self.mail)
        self.assertIn('/clicks/m/', content.alternatives[0][0])

    def test_plaintext_generation(self):
        with patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=get_spam_result_mock):
            self.message.save()

        content = self.message.to_mail(self.mail)
        self.assertIn('/clicks/m/', content.body)

    def test_html_no_unsubscribe_or_viewonline_rewrite(self):
        self.message.track_clicks = True
        self.message.html = '<body><h1>Hi</h1>{}</body>'.format(
            settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        with patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=get_spam_result_mock):
            self.message.save()

        mail = MailFactory(message=self.message)
        content = self.message.to_mail(mail)
        self.assertNotIn('/clicks/m/', content.alternatives[0][0])

    def test_mk_redirection(self):
        mail = MailFactory(message=self.message)
        url = 'http://example.com'
        redir_url = WebVersionLinksRewriter.rewrite(
            mail.identifier,
            self.message.get_app_url(),
            mail.message.msg_links,
            url)

        # build local url from fully qualified url
        local_redir_url = redir_url.split('://')[1].split('/', 1)[1]

        resp = self.client.get('/' + local_redir_url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], url)

    def test_mk_web_redirection(self):
        mail = MailFactory(message=self.message)
        url = 'http://example.com'
        redir_url = WebVersionLinksRewriter.rewrite(
            mail.identifier,
            self.message.get_app_url(),
            mail.message.msg_links,
            url)

        # build local url from fully qualified url
        local_redir_url = redir_url.split('://')[1].split('/', 1)[1]

        self.assertEqual(LinkMap.objects.count(), 1)
        self.assertEqual(TrackRecord.objects.filter(
            kind='click', identifier=mail.identifier).count(), 0)
        resp = self.client.get('/' + local_redir_url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], url)
        self.assertEqual(TrackRecord.objects.filter(
            kind='click', identifier=mail.identifier).count(), 1)

    def test_invalid_tracker(self):
        resp = self.client.get(
            '/t/clicks/m/0202020202020202/CCCCCDDDDD')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'No URL found with this ID')

    def test_html_generation_preserve_doctype(self):
        self.message.track_clicks = True
        self.message.html = (
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
            '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
            '<html xmlns="http://www.w3.org/1999/xhtml">{}</html>').format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER'])
        with patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=get_spam_result_mock):
            self.message.save()

        mail = MailFactory(message=self.message)
        content = self.message.to_mail(mail)
        self.assertIn(
            (
                '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//'
                'EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.'
                'dtd">'),
            content.alternatives[0][0])

    def test_web_version_links_can_track(self):
        self.message.track_clicks = True
        self.message.save()

        mail = MailFactory(message=self.message)

        web_token= WebKey.from_instance(mail.identifier)
        response = self.client.get(
            '/archive/{}/?web_key={}'.format(
                self.message.identifier, web_token.token))

        self.assertIn(b'/t/clicks/w/', response.content)

    def test_web_version_links_can_no_track(self):
        self.message.track_clicks = False
        self.message.save()

        mail = MailFactory(message=self.message)
        web_key = WebKey.from_instance(mail.identifier)
        response = self.client.get(
            '/archive/{}/?web_key={}'.format(
                self.message.identifier, web_key.token))

        self.assertNotIn(b'/t/clicks/w/', response.content)

    def test_web_versions_open_can_no_track(self):
        self.message.track_open = False
        self.message.save()
        mail = MailFactory(message=self.message)
        self.assertNotIn('web_key', mail.web_view_url)

    def test_web_versions_open_can_track(self):
        self.message.track_open = True
        self.message.save()
        mail = MailFactory(message=self.message)
        self.assertIn('web_key', mail.web_view_url)


@override_settings(SECRET_KEY='123412341234')
class TestWebKey(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(author=self.user)
        self.mail = MailFactory(message=self.message)

    def test_mk_web_key(self):
        key = WebKey.from_instance(self.mail.identifier)
        self.assertIsInstance(key.token, str)

    def test_check_web_key(self):
        key = WebKey.from_instance(self.mail.identifier)

        key2 = WebKey(key.token)
        identifier = key2.get_identifier()
        self.assertEqual(identifier, self.mail.identifier)

    def test_check_web_key_bad_sig(self):
        # Sign with a bad key
        with override_settings(SECRET_KEY='2121'):
            web_key = WebKey.from_instance(self.mail.identifier)

        web_key2 = WebKey(web_key.token)
        identifier = web_key2.get_identifier()
        self.assertIsNone(identifier)


class TestContentFilters(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.message = MessageFactory(
            author=self.user, track_clicks=True, track_open=False,
            msg_links={'AAAAABBBBB': 'http://example.com'},
            html='<body><a href="http://example.com">Hi</a>{}</body>'.format(
                settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER']))
        with patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=get_spam_result_mock):
            self.message.save()

    def test_rewrite_footlink(self):
        text = """Hi
        We are [1]

        [1]: http://example.com
        """
        mail = MailFactory(message=self.message)
        out = rewrite_plaintext_links(
            text,
            app_url=self.message.get_app_url(),
            unsubscribe_url=mail.unsubscribe_url,
            mail_identifier=mail.identifier,
            links_map=self.message.msg_links)
        self.assertIn('/clicks/m/', out)

    def test_dont_rewrite_bodylink(self):
        text = """Hi

        Go to http://example.com
        """
        mail = MailFactory(message=self.message)
        out = rewrite_plaintext_links(
            text,
            app_url=self.message.get_app_url(),
            unsubscribe_url=mail.unsubscribe_url,
            mail_identifier=mail.identifier,
            links_map=self.message.msg_links)
        self.assertNotIn('/clicks/m', out)
