from email.utils import parseaddr

from slimta.smtp.reply import Reply
from slimta.queue import QueueError
from slimta.policy import QueuePolicy
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from munch.apps.domains.models import SendingDomain


class Check(QueuePolicy):
    def apply(self, envelope):
        sender_email = parseaddr(envelope.headers.get('From'))[1]

        try:
            validate_email(sender_email)
        except ValidationError:
            sender_email = None

        if not sender_email:
            error = QueueError()
            error.reply = Reply(
                code='554',
                message=(
                    '5.7.1 <{}>: Relay access denied: '
                    'Sending domain invalid').format(envelope.recipients[0]))
            raise error

        organization_domain = SendingDomain.objects.filter(
            organization=envelope.organization)
        domain = organization_domain.get_from_email_addr(
            sender_email, must_raise=False)

        if not domain:
            error = QueueError()
            error.reply = Reply(
                code='554',
                message=(
                    '5.7.1 <{}>: Relay access denied: Sending '
                    'domain for <{}> is not properly configured').format(
                        envelope.recipients[0], sender_email))
            raise error

        envelope.sending_domain = domain
