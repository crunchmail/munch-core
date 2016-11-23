import re
import email
import socket
from collections import OrderedDict
from functools import total_ordering

import dns.resolver
import dns.exception


class SpamCheckerError(Exception):
    def __init__(self, e):
        """
        @param e : the underlying exception
        """
        self.sub_e = e

    def __str__(self):
        return str(self.sub_e)


class SpamChecker:
    def __init__(self, service_name=None, host=None, port=None):
        self.service_name = service_name

        if host and port:
            self.host = host
            self.port = int(port)
        else:
            # first, resolve the host/port from service name
            try:
                results = dns.resolver.query(service_name, 'SRV')
                prio, weight, port, target = results[0].to_text().split(' ')
            except dns.exception.DNSException as e:
                raise SpamCheckerError(e)

            self.port = int(port)
            self.host = target

    def check(self, msg):
        """
        @param msg : a string containing the message to check
        @return status, score, message
        """
        msg_bytes = msg.encode()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((self.host, self.port))
            s.sendall(b'PROCESS SPAMC/1.4')
            s.sendall(b"\r\n")
            s.sendall(("Content-length: %s" % len(msg_bytes)).encode())
            s.sendall(b"\r\n")
            s.sendall(b"\r\n")
            s.sendall(msg_bytes)
            s.shutdown(1)
            socketfile = s.makefile("rb")
            line1_info = socketfile.readline()
            socketfile.readline()
            socketfile.readline()
            socketfile.readline()
            content = socketfile.read()
            if len(line1_info) == 0:
                raise SpamCheckerError("Spamd response is empty")

            answer = line1_info.strip().split()
            if len(answer) != 3:
                raise SpamCheckerError("Invalid Spamd answer: {}".format(
                    answer))
            (version, number, status) = answer
            if status.decode() != 'EX_OK':
                raise SpamCheckerError('Invalid Spamd status: {}'.format(
                    status))

        except (socket.error) as e:
            raise SpamCheckerError(e) from None

        else:
            # parse mail
            return SpamResult.from_headers(email.message_from_bytes(content))


class SpamResult:
    SPAM_STATUS_HEADER = 'X-Spam-Status'
    SPAM_REPORT_HEADER = 'X-Spam-Report'

    r_spam_status = re.compile(
        r'\s*(?P<is_spam>Yes|No),.*\s+score=(?P<score>\-?\d+\.\d+) .*',
        re.MULTILINE | re.DOTALL)
    r_spam_report = re.compile((
        r'\s+\*\s+(?P<score>\d+\.\d+)\s+(?P<name>[A-Z0-9_]+)'
        r'\s+(?P<main_content>.*)'
        r'(\n\s+\*      (?P<extra_content>.*))*'), re.MULTILINE)

    def __init__(self, score, is_spam, checks, error=None):
        self.score = float(score)
        self.is_spam = is_spam
        self._checks = checks
        self.error = error

    @classmethod
    def from_headers(cls, headers):
        for i in (cls.SPAM_STATUS_HEADER, cls.SPAM_REPORT_HEADER):
            if i not in headers:
                raise SpamCheckerError('Header {} not present'.format(i))
        status = headers[cls.SPAM_STATUS_HEADER]
        score = cls.r_spam_status.match(status).group('score')
        is_spam = cls.r_spam_status.match(status).group('is_spam') == 'Yes'

        checks = []
        for m in cls.r_spam_report.finditer(headers[cls.SPAM_REPORT_HEADER]):
            name = m.group('name')
            check_score = m.group('score')
            description = m.group('main_content')
            if m.group('extra_content'):
                description += ' ' + m.group('extra_content')
            checks.append(SpamCheckResult(check_score, name, description))
        return cls(score, is_spam, checks)

    def serialize(self):
        return OrderedDict((
            ('error', self.error),
            ('is_spam', None if self.error else self.is_spam),
            ('score', None if self.error else self.score),
            ('checks',
             [i.serialize() for i in sorted(self._checks, reverse=True)])))

    @property
    def checks(self):
        return [i.serialize() for i in sorted(self._checks, reverse=True)]


@total_ordering
class SpamCheckResult:
    def __init__(self, score, name, description):
        self.score = float(score)
        self.name = name
        self.description = description

    def __str__(self):
        return '{}: {}'.format(self.name, self.score)

    def serialize(self):
        return {
            'name': self.name,
            'score': self.score,
            'description': self.description
        }

    def __lt__(self, other):
        return self.score < other.score
