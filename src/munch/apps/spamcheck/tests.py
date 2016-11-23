import math
import email
import unittest
import logging

import clamd

from django.test import TestCase
from django.conf import settings

from . import SpamChecker, SpamCheckerError, SpamResult


logging.disable(logging.CRITICAL)


SAMPLE_HAM = """Return-Path: Foo@example.com
Delivery-Date: Mon May 13 04:46:13 2013
Received: from mandark.labs.netnoteinc.com ([213.105.180.140]) by
    dogma.slashnull.org (8.11.6/8.11.6) with ESMTP id g4D3kCe15097 for
    <jm@jmason.org>; Mon, 13 May 2013 04:46:12 +0100
Message-ID: <53E4FAB7.903@example.com>
Date: Fri, 13 May 2013 04:40:39 +0100
From: Foo <Foo@example.com>
User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:24.0) Gecko/20100101 Icedove/24.6.0
MIME-Version: 1.0
To: Bar <Bar@example.com>
Subject: Reunion prochaine
Content-Type: text/plain; charset=UTF-8; format=flowed
Content-Transfer-Encoding: 8bit

Salut,

A bientôt pour une super reunion

Bien a toi,

--
   Foo
"""
SAMPLE_SPAM = """
Return-Path: merchantsworld2001@juno.com
Delivery-Date: Mon May 13 04:46:13 2002
Received: from mandark.labs.netnoteinc.com ([213.105.180.140]) by
    dogma.slashnull.org (8.11.6/8.11.6) with ESMTP id g4D3kCe15097 for
    <jm@jmason.org>; Mon, 13 May 2002 04:46:12 +0100
Received: from 203.129.205.5.205.129.203.in-addr.arpa ([203.129.205.5]) by
    mandark.labs.netnoteinc.com (8.11.2/8.11.2) with SMTP id g4D3k2D12605 for
    <jm@netnoteinc.com>; Mon, 13 May 2002 04:46:04 +0100
Received: from html (unverified [207.95.174.49]) by
    203.129.205.5.205.129.203.in-addr.arpa (EMWAC SMTPRS 0.83) with SMTP id
    <B0000178595@203.129.205.5.205.129.203.in-addr.arpa>; Mon, 13 May 2002
    09:04:46 +0530
Message-Id: <B0000178595@203.129.205.5.205.129.203.in-addr.arpa>
From: lmrn@mailexcite.com
To: ranmoore@cybertime.net
Subject: Real Protection, Stun Guns!  Free Shipping! Time:2:01:35 PM
Date: Mon, 28 Jul 1980 14:01:35
MIME-Version: 1.0
X-Keywords:
Content-Type: text/html; charset="DEFAULT"

<html>
<body>
<center>
<h3>
<font color="blue">
<b>
The Need For Safety Is Real In 2002, You Might Only Get One Chance - Be Ready!
<p>
Free Shipping & Handling Within The (USA) If You Order Before May 25, 2002!
<p>
3 Day Super Sale, Now Until May 7, 2002!  Save Up To $30.00 On Some Items!

</b>
</font>
</h3>
</center>
<p>
IT'S GETTING TO BE SPRING AGAIN, PROTECT YOURSELF AS YOU WALK,<br>
JOG AND EXERCISE OUTSIDE.  ALSO PROTECT YOUR LOVED ONES AS<br>
THEY RETURN HOME FROM COLLEGE!<br>
<p>
*     LEGAL PROTECTION FOR COLLEGE STUDENTS!<br>
*     GREAT UP'COMING OUTDOOR PROTECTION GIFTS!<br>
*     THERE IS NOTHING WORTH MORE PROTECTING THAN LIFE!<br>
*     OUR STUN DEVICES & PEPPER PRODUCTS ARE LEGAL PROTECTION!
<p>
<b>
<font color="red">
JOIN THE WAR ON CRIME!
</b>
</font>
<p>

STUN GUNS AND BATONS
<p>
EFFECTIVE - SAFE - NONLETHAL
<p>
PROTECT YOUR LOVED ONES AND YOURSELF
<p>
No matter who you are, no matter what City or Town you live in,<br>
if you live in America, you will be touched by crime.
<p>
You hear about it on TV.  You read about it in the newspaper.<br>
It's no secret that crime is a major problem in the U.S. today.<br>
Criminals are finding it easier to commit crimes all the time.
<p>
Weapons are readily available.  Our cities' police forces have<br>
more work than they can handle.  Even if these criminal are<br>
caught, they won't be spending long in our nation's overcrowded<br>
jails.  And while lawmakers are well aware of the crime problem,<br>
they don't seem to have any effective answers.
<p>
Our Email Address:  <a
href="mailto:Merchants4all@aol.com">Merchants4all@aol.com</a>
<p>
INTERESTED:
<p>
You will be protecting yourself within 7 days!  Don't Wait,<br>
visit our web page below, and join The War On Crime!
<p>
*****************<br>
<a
href="http://www.geocities.com/realprotection_20022003/">http://www.geocities.com/realprotection_20022003/</a><br>
*****************
<p>
Well, there is an effective answer.  Take responsibility for<br>
your own security.  Our site has a variety of quality personal<br>
security products.  Visit our site, choose the personal security<br>
products that are right for you.  Use them, and join the war on
crime!
<p>
FREE PEPPER SPRAY WITH ANY STUN UNIT PURCHASE.<br>
(A Value of $15.95)
<p>
We Ship Orders Within 5 To 7 Days, To Every State In The U.S.A.<br>
by UPS, FEDEX, or U.S. POSTAL SERVICE.  Visa, MasterCard, American<br>
Express & Debt Card Gladly Accepted.
<p>
Ask yourself this question, if you don't help your loved ones,
who will?
<p>
INTERESTED:
<p>
*****************<br>
<a
href="http://www.geocities.com/realprotection_20022003/">http://www.geocities.com/realprotection_20022003/</a><br>
*****************
<p>
___The Stun Monster 625,000 Volts ($86.95)<br>
___The Z-Force Slim Style 300,000 Volts ($64.95)<br>
___The StunMaster 300,000 Volts Straight ($59.95)<br>
___The StunMaster 300,000 Volts Curb ($59.95)<br>
___The StunMaster 200,000 Volts Straight ($49.95)<br>
___The StunMaster 200,000 Volts Curb ($49.95)<br>
___The StunBaton 500,000 Volts ($89.95)<br>
___The StunBaton 300,000 Volts ($79.95)<br>
___Pen Knife (One $12.50, Two Or More $9.00)<br>
___Wildfire Pepper Spray  (One $15.95, Two Or More $11.75)
<p>
___Add $5.75 For Shipping & Handling Charge.
<p>

To Order by postal mail, please send to the below address.<br>
Make payable to Mega Safety Technology.
<p>
Mega Safety Technology<br>
3215 Merrimac Ave.<br>
Dayton, Ohio  45405<br>
Our Email Address:  <a
href="mailto:Merchants4all@aol.com">Merchants4all@aol.com</a>
<p>
Order by 24 Hour Fax!!!  775-257-6657.
<p>
*****<br>
<b><font color="red">Important Credit Card Information! Please Read Below!</b></font>
 <br><br>
*     Credit Card Address, City, State and Zip Code, must match
      billing address to be processed.
<br><br>

CHECK____  MONEYORDER____  VISA____ MASTERCARD____ AmericanExpress___
Debt Card___
<br><br>
Name_______________________________________________________<br>
(As it appears on Check or Credit Card)
<br><br>
Address____________________________________________________<br>
(As it appears on Check or Credit Card)
<br><br>
___________________________________________________<br>
City,State,Zip(As it appears on Check or Credit Card)
<br><br>
___________________________________________________<br>
Country
<br><br>
___________________________________________________<br>
(Credit Card Number)
<br><br>
Expiration Month_____  Year_____
<br><br>
___________________________________________________<br>
Authorized Signature
<br><br>
<b>
*****IMPORTANT NOTE*****
</b>
<br><br>
If Shipping Address Is Different From The Billing Address Above,
Please Fill Out Information Below.
<br><br>
Shipping Name______________________________________________
<br><br>
Shipping Address___________________________________________
<br><br>
___________________________________________________________<br>
Shipping City,State,Zip
<br><br>
___________________________________________________________<br>
Country
<br><br>
___________________________________________________________<br>
Email Address & Phone Number(Please Write Neat)
</body>
</html>
"""


def get_spam_result_mock(msg, is_spam=False, score=0.0, checks=5):
    """
    @param msg : a string containing the message to check
    @param is_spam : a boolean that turn email as spam or not(default: False)
    @param score : a float that reflect spam checker score
    @param checks : a interger that reflect the number of checks done on email
    @return SpamResult
    """
    checks_separator = '\n\t*  '
    checks_examples = (
        '%0.1f NO_RELAYS Informational: message was not relayed via SMTP',
        '%0.1f WEIRD_PORT URI: Uses non-standard port number for HTTP',
        '%0.1f HTML_MESSAGE BODY: HTML included in message',
        '%0.1f MISSING_HEADERS Missing To: header',
        '%0.1f LOTS_OF_MONEY Huge... sums of money',
        '%0.1f MONEY_FORM Lots of money if you fill out a form',
        '%0.1f MISSING_DATE Missing Date: header',
        '%0.1f MISSING_MID Missing Message-Id: header',
        '%0.1f MISSING_SUBJECT Missing Subject: header',
        '%0.1f MISSING_FROM Missing From: header',
        '%0.1f NO_HEADERS_MESSAGE Message appears to be missing most RFC-822',
        '%0.1f FILL_THIS_FORM Fill in a form with personal information',
        '%0.1f NORMAL_HTTP_TO_IP URI: Uses a dotted-decimal IP address in URL',
        '%0.1f NO_RECEIVED Informational: message has no Received headers')
    spam_status_template = (
        '%s, score=%s required=5.0 tests=HTML_MESSAGE,NO_RECEIVED,'
        '\n\tNO_RELAYS,WEIRD_PORT autolearn=unavailable '
        'autolearn_force=no version=3.4.0')

    msg_as_email = email.message_from_bytes(msg.encode())

    if checks > len(checks_examples):
        raise Exception("SpamCheckerMock doesn't have enough checks examples")

    is_spam_str = "No"
    if is_spam:
        is_spam_str = "Yes"
        # Default `score` and `checks` for spam if not given
        if not score:
            score = 5.1
        if not checks:
            checks = 5
    msg_as_email.add_header(
        'X-Spam-Status', spam_status_template % (is_spam_str, score))

    # Generate X-Spam-Report based on `checks`
    report_header = ""
    # >>> math.modf(5.1)
    # >>> (0.09, 5.0)
    floating_score, rest_score = math.modf(score)
    for i in range(0, checks):
        check_score = rest_score / checks
        if i == 0:
            check_score += floating_score
        report_header += checks_separator
        report_header += checks_examples[i] % check_score
    msg_as_email.add_header('X-Spam-Report', report_header)
    return SpamResult.from_headers(msg_as_email)


def clamd_check_virus_mock(afile, is_virus=False):
    if afile.read() == clamd.EICAR or is_virus:
        return {'stream': ('FOUND', '')}
    return {'stream': ('NOT FOUND', '')}


class SpamCheckerDNSTest(TestCase):
    def test_invalid_host(self):
        with self.assertRaises(SpamCheckerError):
            sc = SpamChecker('inexistent.example.com')

    def test_norespond_host(self):
        with self.assertRaises(SpamCheckerError):
            sc = SpamChecker('example.com')

    def test_ok_host(self):
        sc = SpamChecker(host=settings.SPAMD_HOST, port=settings.SPAMD_PORT)
        self.assertIsInstance(sc.host, str)
        self.assertIsInstance(sc.port, int)


class SpamCheckerTest(TestCase):
    def setUp(self):
        self.sc = SpamChecker(host=settings.SPAMD_HOST, port=settings.SPAMD_PORT)

    def test_check_ham(self):
        with unittest.mock.patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=lambda *args, **kwargs: get_spam_result_mock(
                    is_spam=False, score=2.4, checks=1, *args, **kwargs)):
            res = self.sc.check(SAMPLE_HAM)
        self.assertEqual(res.is_spam, False)
        self.assertEqual(res.score, 2.4)
        self.assertEqual(len(res.checks), 1)

    def test_check_spam(self):
        with unittest.mock.patch(
                'munch.apps.spamcheck.SpamChecker.check',
                side_effect=lambda *args, **kwargs: get_spam_result_mock(
                    is_spam=True, score=5.4, checks=10, *args, **kwargs)):
            res = self.sc.check(SAMPLE_SPAM)
        self.assertEqual(res.is_spam, True)
        self.assertEqual(res.score, 5.4)
        self.assertEqual(len(res.checks), 10)


class SpamResultTest(TestCase):
    def test_parsing(self):
        headers = {
            'X-Spam-Status': """Yes, score=9.8 required=5.0 tests=[DATE_IN_PAST_96_XX=2.6,
        FILL_THIS_FORM=0.001, FREEMAIL_ENVFROM_END_DIGIT=0.25,
        FREEMAIL_FORGED_FROMDOMAIN=0.001, FREEMAIL_FROM=0.001,
        HEADER_FROM_DIFFERENT_DOMAINS=0.001, HTML_MESSAGE=0.001, LOTS_OF_MONEY=0.001,
        MIME_HTML_ONLY=2.199, MONEY_FORM=2.301, RDNS_NONE=2.399] autolearn=disabled""",
            'X-Spam-Report':"""
        *  0.2 FREEMAIL_ENVFROM_END_DIGIT Envelope-from freemail username ends in
        *      digit (merchantsworld2001[at]juno.com)
        *  2.6 DATE_IN_PAST_96_XX Date: is 96 hours or more before Received: date
        *  0.0 FREEMAIL_FROM Sender email is commonly abused enduser mail provider
        *      (merchantsworld2001[at]juno.com)
        *  0.0 HEADER_FROM_DIFFERENT_DOMAINS From and EnvelopeFrom 2nd level mail
        *      domains are different""",
            'X-Spam-Flag': 'YES'
        }

        sr = SpamResult.from_headers(headers)
        self.assertEqual(sr.is_spam, True)
        self.assertEqual(sr.score, 9.8)
        self.assertEqual(len(sr.checks), 4)
        self.assertEqual(
            sr.checks[3]['description'],
            'From and EnvelopeFrom 2nd level mail domains are different')
        self.assertEqual(sr.checks[3]['score'], 0)
        self.assertEqual(sr.checks[3]['name'],'HEADER_FROM_DIFFERENT_DOMAINS')
