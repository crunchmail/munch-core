from rest_framework import serializers
from rest_framework.serializers import ValidationError

from munch.core.utils.serializers import HALLinksField
from munch.core.utils.serializers import CurrentOrganizationDefault

from ...models import SendingDomain


class AltOrganizationsField(serializers.HyperlinkedRelatedField):
    def get_queryset(self, *args, **kwargs):
        return self.context.get('request').user.organization.children.all()


class SendingDomainSerializer(serializers.HyperlinkedModelSerializer):
    dkim_status = serializers.ReadOnlyField(allow_null=True)
    app_domain_status = serializers.ReadOnlyField(allow_null=True)
    _links = HALLinksField(
        nested_endpoints=['revalidate'],
        view_name='domains:sendingdomain-detail')
    alt_organizations = AltOrganizationsField(
        many=True, view_name='users:organization-detail', required=False)
    organization = serializers.HiddenField(
        default=serializers.CreateOnlyDefault(CurrentOrganizationDefault()))

    class Meta:
        model = SendingDomain
        fields = [
            'url', 'name', 'dkim_status', 'app_domain_status',
            'organization', 'alt_organizations', 'app_domain',
            'app_domain_status_date', 'dkim_status_date', '_links']
        read_only_fields = [
            'organization', 'dkim_status_date', 'app_domain_status_date']
        extra_kwargs = {'url': {'view_name': 'domains:sendingdomain-detail'}}

    def validate(self, attrs):
        for organization in attrs.get('alt_organizations', []):
            if organization.parent_id != attrs.get('organization').id:
                raise ValidationError('Invalid organization')
        return attrs
