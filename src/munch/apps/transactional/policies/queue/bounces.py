import logging

from django.conf import settings
from django.db.models import Prefetch
from slimta.policy import QueuePolicy
from slimta.queue import QueueError
from slimta.smtp.reply import Reply

from munch.apps.optouts.models import OptOut
from munch.apps.users.models import MunchUser
from munch.apps.users.models import Organization
from munch.apps.users.models import SmtpApplication

logger = logging.getLogger(__name__)


class Check(QueuePolicy):
    def apply(self, envelope):
        error = QueueError()
        error.reply = Reply(
            code='521',
            message='5.7.1 Email to this recipient will not be delivered')

        if OptOut.objects.filter(
                origin=OptOut.BY_BOUNCE,
                address=envelope.recipients[0]).exists():
            raise error

        # Sorry about that, it's just a big query set with prefetch related
        user = SmtpApplication.objects.prefetch_related(
            Prefetch(
                'author',
                MunchUser.objects.prefetch_related(
                    Prefetch('organization', Organization.objects.all().only(
                        'id'))).all().only('organization'))).only(
                            'author').get(username=envelope.client.get(
                                'auth')[0]).author

        # Attach theses attributs to envelope to avoid re-requesting it later
        envelope.user = user
        envelope.organization = user.organization

        category = envelope.headers.get(
            settings.TRANSACTIONAL.get(
                'X_MAIL_BATCH_CATEGORY_HEADER', None))
        if category:
            if OptOut.objects.exclude(
                    origin=OptOut.BY_BOUNCE).filter(
                        author__organization=envelope.organization,
                        category__name=category).exists():
                raise error
        else:
            if OptOut.objects.exclude(
                    origin=OptOut.BY_BOUNCE).filter(
                        author__organization=envelope.organization).exists():
                raise error
