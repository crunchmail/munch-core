import django_filters

from munch.core.utils.filters import DRFFilterSet

from ...models import Mail
from ...models import Message
from ...models import MailStatus


class MessageFilter(DRFFilterSet):
    status = django_filters.MultipleChoiceFilter(
        choices=Message.STATUS_CHOICES)

    class Meta:
        model = Message
        fields = [
            'creation_date', 'status', 'category', 'sender_email',
            'track_open', 'track_clicks', 'external_optout', 'is_spam']
        # default order by -creation_date
        order_by = ['-' + i for i in fields] + [i for i in fields]


class MailFilter(DRFFilterSet):
    last_status = django_filters.CharFilter(name='curstatus')
    opened = django_filters.MethodFilter(action='_opened')
    clicked = django_filters.MethodFilter(action='_clicked')
    to = django_filters.CharFilter(name='recipient')
    delivery_status = django_filters.MultipleChoiceFilter(
        name='curstatus', choices=MailStatus.STATUS_CHOICES)

    class Meta:
        model = Mail
        # TODO: To must be recipient in v2
        fields = {
            'to': ['exact'],
            'last_status': ['exact'],
            'delivery_status': ['exact'],
            'source_ref': ['exact', 'startswith'],
            'source_type': ['exact']}
        order_by = True

    def _opened(self, queryset, value):
        # Watch out, putting the same name for method and filter field
        # overwrites the field
        return queryset.opened()

    def _clicked(self, queryset, value):
        return queryset.clicked()


class MailStatusFilter(DRFFilterSet):
    address = django_filters.CharFilter(name='mail__recipient')

    class Meta:
        model = MailStatus
        fields = ['address', 'creation_date', 'status']
        order_by = True
