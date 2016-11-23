from rest_framework import serializers

from munch.core.utils.serializers import HALLinksField

from ...models import Mail
from ...models import MailBatch
from ...models import MailStatus


class NestedTrackingSummarySerializer(serializers.Serializer):
    opened = serializers.DateTimeField(source='first_open')
    open_time = serializers.IntegerField()
    clicked = serializers.ListField(
        source='clicks', child=serializers.DictField())


class MailStatusSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = MailStatus
        fields = ['status', 'creation_date', 'status_code', 'raw_msg']


class MailSerializer(serializers.HyperlinkedModelSerializer):
    last_status = MailStatusSerializer(read_only=True)
    tracking = NestedTrackingSummarySerializer(
        read_only=True, source='tracking_info')
    _links = HALLinksField(
        nested_endpoints=['statuses'],
        view_name='transactional:mail-detail')

    class Meta:
        model = Mail
        fields = [
            'url', 'identifier', 'sender', 'creation_date', 'last_status',
            'tracking', 'batch', 'track_open', 'track_clicks', '_links']
        extra_kwargs = {
            'url': {'view_name': 'transactional:mail-detail'},
            'batch': {'view_name': 'transactional:batch-detail'}}


class MailBatchSerializer(serializers.HyperlinkedModelSerializer):
    _links = HALLinksField(
        nested_endpoints=['mails', 'stats', 'bounces', 'opt_outs'],
        view_name='transactional:batch-detail')

    class Meta:
        model = MailBatch
        fields = ['url', 'creation_date', 'name', 'category', '_links']
        extra_kwargs = {
            'url': {'view_name': 'transactional:batch-detail'},
            'category': {'view_name': 'core:category-detail'}}
