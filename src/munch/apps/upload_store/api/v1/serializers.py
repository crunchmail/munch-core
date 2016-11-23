from rest_framework import serializers

from ...models import Image


class ImageSerializer(serializers.HyperlinkedModelSerializer):
    expiration = serializers.DurationField(required=False)
    url = serializers.HyperlinkedIdentityField(
        view_name='v1:upload-store:image-detail',
        lookup_field='hash', lookup_url_kwarg='pk')

    class Meta:
        model = Image
        fields = ('url', 'file', 'width', 'upload_date', 'expiration')
        read_only_fields = ('upload_date',)

    def create(self, valid_data):
        organization = self.context['request'].user.organization
        valid_data['organization'] = organization
        return super().create(valid_data)
