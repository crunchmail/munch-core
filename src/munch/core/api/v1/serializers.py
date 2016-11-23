from rest_framework import serializers

from ...models import Category
from ...utils.serializers import HALLinksField


class CategorySerializer(serializers.HyperlinkedModelSerializer):
    _links = HALLinksField(
        nested_endpoints=[
            'opt_outs', 'stats', 'messages_stats'],
        view_name='core:category-detail')
    batches = serializers.HyperlinkedRelatedField(
        read_only=True, view_name='transactional:batch-detail',
        many=True, source='mailbatches')
    messages = serializers.HyperlinkedRelatedField(
        read_only=True, view_name='campaigns:message-detail', many=True)

    class Meta:
        model = Category
        fields = ('url', 'name', 'messages', 'batches', '_links')
        extra_kwargs = {'url': {'view_name': 'core:category-detail'}}
