from rest_framework import serializers

from ...models import OptOut


class OptOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = OptOut
        fields = ['identifier', 'address', 'creation_date', 'origin']
        read_only_fields = ['identifier', 'address']
