import logging
from datetime import datetime
from unittest.mock import patch
from unittest.mock import MagicMock

import celery
import requests
from django.test import TestCase
from django.conf import settings
from libfaketime import fake_time
from slimta.smtp.reply import Reply
from slimta.envelope import Envelope

from munch.core.mail.utils import mk_base64_uuid

from ..status import send_webhook
from ..status import handle_dsn_status
from ..status import handle_smtp_status

from .factories import MailFactory


def mock_status(status_code):
    m = MagicMock()
    m.status_code = status_code
    return m


class TestDSNStatus(TestCase):
    def setUp(self):
        identifier = mk_base64_uuid()
        self.mail = MailFactory(
            identifier=identifier,
            headers={
                'To': 'someone@example.com',
                'Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)',
                settings.TRANSACTIONAL['X_MESSAGE_ID_HEADER']: identifier,
                settings.TRANSACTIONAL['X_HTTP_DSN_RETURN_PATH_HEADER']: 'http://example.com/ping',  # noqa
            })

    def test_push_dsn_status(self):
        with patch('requests.post', return_value=mock_status(200)):
            handle_dsn_status(
                (
                    'To: return-{}@test.munch.example.com\n'
                    'Date: Fri,  5 Aug 2014 23:35:50 +0700 (WIT)').format(
                        self.mail.identifier),
                {
                    'Diagnostic-Code': 'smtp; 200 Delivered',
                    'Status': '2.0.0',
                    'Arrival-Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)',
                    'Final-Recipient': 'foo@bar'
                }
            )
            requests.post.assert_called_with('http://example.com/ping', json={
                'status': 'delivered',
                'message': 'smtp; 200 Delivered',
                'esmtp_status': '2.0.0',
                'smtp_status': '200',
                'date': '2014-08-05T16:35:50+00:00',
                'recipient': 'foo@bar'
            })

    def test_push_dsn_status_no_smtp_diagnostic(self):
        with patch('requests.post', return_value=mock_status(200)):
            handle_dsn_status(
                (
                    'To: return-{}@test.munch.example.com\n'
                    'Date: Fri,  5 Aug 2014 23:35:50 +0700 (WIT)').format(
                        self.mail.identifier),
                {
                    'Diagnostic-Code': 'FreeForm!',
                    'Status': '2.0.0',
                    'Arrival-Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)',
                    'Final-Recipient': 'foo@bar'
                }
            )
            requests.post.assert_called_with('http://example.com/ping', json={
                'status': 'delivered',
                'message': 'FreeForm!',
                'esmtp_status': '2.0.0',
                'smtp_status': 'unknown',
                'date': '2014-08-05T16:35:50+00:00',
                'recipient': 'foo@bar'
            })

    def test_push_dsn_status_no_arrival_date_nor_date(self):
        with fake_time('2015-12-18'):
            with patch('requests.post', return_value=mock_status(200)):
                handle_dsn_status(
                    'To: return-{}@test.munch.example.com'.format(
                        self.mail.identifier),
                    {
                        'Diagnostic-Code': 'FreeForm!',
                        'Status': '2.0.0',
                        'Final-Recipient': 'foo@bar'
                    }
                )
                requests.post.assert_called_with(
                    'http://example.com/ping',
                    json={
                        'status': 'delivered',
                        'message': 'FreeForm!',
                        'esmtp_status': '2.0.0',
                        'smtp_status': 'unknown',
                        'date': '2015-12-18T00:00:00',
                        'recipient': 'foo@bar'
                    })

    def test_push_dsn_status_no_arrival_date(self):
        with fake_time('2015-12-18'):
            with patch('requests.post', return_value=mock_status(200)):
                handle_dsn_status(
                    (
                        'To: return-{}@test.munch.example.com\n'
                        'Date: Fri,  5 Aug 2014 23:35:50 +0700 (WIT)').format(
                            self.mail.identifier),
                    {
                        'Diagnostic-Code': 'FreeForm!',
                        'Status': '2.0.0',
                        'Final-Recipient': 'foo@bar'
                    }
                )
                requests.post.assert_called_with(
                    'http://example.com/ping',
                    json={
                        'status': 'delivered',
                        'message': 'FreeForm!',
                        'esmtp_status': '2.0.0',
                        'smtp_status': 'unknown',
                        'date': '2014-08-05T16:35:50+00:00',
                        'recipient': 'foo@bar'
                    }
                )

    def test_push_dsn_status_webhook_error(self):
        with self.assertRaises(celery.exceptions.Retry):
            with patch('requests.post', return_value=mock_status(500)):
                send_webhook(
                    self.mail.identifier,
                    {
                        'To': 'return-{}@test.munch.example.com'.format(
                            self.mail.identifier),
                        'Date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)',
                        'Diagnostic-Code': 'smtp; 200 Delivered',
                        'Status': '2.0.0',
                        'Arrival-Date': 'Fri, 5 Aug 2014 23:35:50 +0700 (WIT)',
                    },
                    {
                        'status': 'Delivered',
                        'message': '200 Delivered',
                        'smtp_status': 'delivered',
                        'esmtp_status': '2.0.0',
                        'date': 'Fri,  5 Aug 2014 23:35:50 +0700 (WIT)',
                        'recipient': ''
                    })

    def test_push_dsn_status_broken_headers(self):
        with self.assertRaises(celery.exceptions.Reject):
            with patch('requests.post', return_value=mock_status(201)):
                handle_dsn_status(
                    'Date: Fri,  5 Aug 2014 23:35:50 +0700 (WIT)',
                    {
                        'Diagnostic-Code': 'smtp; 200 Delivered',
                        'Status': '2.0.0',
                        'Arrival-Date': 'Fri, 5 Aug 2014 23:35:50 +0700 (WIT)',
                    }
                )
                requests.post.assert_called_with(
                    'http://example.com/ping',
                    json={
                        'status': 'delivered',
                        'message': 'smtp; 200 Delivered',
                        'smtp_status': '2.0.0',
                        'date': '2014-08-05T16:35:50+00:00',
                        'recipient': ''
                    })

    def test_push_dsn_status_missing_esmtp_code(self):
        with self.assertRaises(celery.exceptions.Reject):
            with patch('requests.post', return_value=mock_status(201)):
                handle_dsn_status(
                    (
                        'To: return-{}@test.munch.example.com\n'
                        'Date: Fri,  5 Aug 2014 23:35:50 +0700 (WIT)').format(
                            self.mail.identifier),
                    {
                        'Diagnostic-Code': 'smtp; 200 Delivered'
                    }
                )

    def test_push_dsn_status_unknown_email(self):
        with self.assertRaises(celery.exceptions.Reject):
            with patch('requests.post', return_value=mock_status(201)):
                # This status is unknown to the DB
                handle_dsn_status(
                    (
                        'To: return-4242424242424242424242@'
                        'test.munch.example.com\n'
                        'Date: Fri,  5 Aug 2014 23:35:50 +0700 (WIT)'),
                    {
                        'Diagnostic-Code': 'smtp; 200 Delivered'
                    }
                )

    def test_push_smtp_status(self):
        body = (
            "Return-Path: return-{}@test.munch.example.com\n"
            "X-CM-Message-Id: {}".format(
                self.mail.identifier, self.mail.identifier))
        env = Envelope()
        env.parse(body.encode('utf-8'))
        reply = Reply('200', '2.0.0 Delivered')

        with patch('requests.post', return_value=mock_status(201)):
            with fake_time('2015-12-18'):
                handle_smtp_status(
                    'delivered', datetime.now(),
                    '{}'.format(self.mail.identifier), reply, 'localhost')

            requests.post.assert_called_with(
                'http://example.com/ping',
                json={
                    'status': 'delivered',
                    'message': '2.0.0 Delivered',
                    'smtp_status': '200',
                    'esmtp_status': '2.0.0',
                    'date': '2015-12-18T00:00:00',
                    'recipient': ''
                })

    def test_push_smtp_status_no_http_returnpath(self):
        mail = MailFactory()
        env = Envelope()
        env.parse("Return-Path: return-{}@test.munch.example.com".format(
            mail.identifier).encode('utf-8'))
        reply = Reply('200', '2.0.0 Delivered')

        with patch('requests.post'):
            with patch('logging.warning'):
                handle_smtp_status(
                    'delivered', datetime.now(),
                    mail.identifier, reply, 'localhost')

                requests.post.assert_not_called()
                logging.warning.assert_called()
