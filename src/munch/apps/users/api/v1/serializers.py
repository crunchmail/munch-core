from django.db.models import Q
from django.contrib.auth.models import Group
from django.contrib.auth import authenticate
from django.utils.translation import ugettext as _
import rest_framework_jwt.settings
from rest_framework import serializers
from rest_framework.serializers import ValidationError
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_jwt.compat import PasswordField
from rest_framework_jwt.serializers import JSONWebTokenSerializer

from munch.core.utils.serializers import HALLinksField
from munch.core.utils.relations import ScopedHyperLinkedRelatedField

from ...utils import UserDisabledException
from ...models import MunchUser
from ...models import Organization
from ...models import APIApplication
from ...models import SmtpApplication
from ...models import OrganizationSettings


class MeSerializer(serializers.HyperlinkedModelSerializer):
    groups = serializers.SlugRelatedField(
        slug_field='name', many=True,
        queryset=Group.objects.all(), required=False)

    _links = HALLinksField(
        nested_endpoints=['regen_secret', 'change_password'],
        view_name='users:munchuser-detail')

    class Meta:
        model = MunchUser
        fields = [
            'identifier', 'first_name', 'last_name', 'secret', 'groups',
            'organization', '_links']
        extra_kwargs = {
            'organization': {'view_name': 'users:organization-detail'}}

    def validate(self, attrs):
        super().validate()
        for field in ('first_name', 'last_name'):
            if field in attrs and attrs[field] == '':
                raise ValidationError(_(
                    '{} cannot be empty'.format(field)))


class APIApplicationSerializer(serializers.HyperlinkedModelSerializer):
    _links = HALLinksField(
        nested_endpoints=['regen_secret'],
        view_name='users:applications-api-detail')

    class Meta:
        model = APIApplication
        fields = ['url', 'identifier', 'secret', '_links']
        read_only_fields = ['secret']
        extra_kwargs = {'url': {'view_name': 'users:applications-api-detail'}}

    def validate(self, attrs):
        identifier = attrs.get('identifier')
        try:
            application = APIApplication.objects.get(
                author=self.context.get('request').user, identifier=identifier)
        except APIApplication.DoesNotExist:
            return attrs
        if self.instance and application.id == self.instance.id:
            return attrs
        else:
            raise ValidationError(_(
                'You already own an api application with this identifier'))


class SmtpApplicationSerializer(serializers.HyperlinkedModelSerializer):
    _links = HALLinksField(
        nested_endpoints=['regen_credentials'],
        view_name='users:applications-smtp-detail')

    class Meta:
        model = SmtpApplication
        fields = ['url', 'username', 'secret', 'identifier', '_links']
        read_only_fields = ['username', 'secret']
        extra_kwargs = {'url': {'view_name': 'users:applications-smtp-detail'}}

    def validate(self, attrs):
        identifier = attrs.get('identifier')
        try:
            application = SmtpApplication.objects.get(
                author=self.context.get('request').user, identifier=identifier)
        except SmtpApplication.DoesNotExist:
            return attrs
        if self.instance and application.id == self.instance.id:
            return attrs
        else:
            raise ValidationError(_(
                'You already own an smtp application with this identifier'))


class MunchUserSerializer(serializers.HyperlinkedModelSerializer):
    api_key = serializers.ReadOnlyField(source='secret')
    groups = serializers.SlugRelatedField(
        slug_field='name', many=True,
        queryset=Group.objects.all(), required=False)

    _links = HALLinksField(
        nested_endpoints=['regen_secret', 'change_password'],
        view_name='users:munchuser-detail')

    class Meta:
        model = MunchUser
        fields = [
            'url', 'identifier', 'first_name', 'last_name', 'groups',
            'api_key', '_links']
        extra_kwargs = {'url': {'view_name': 'users:munchuser-detail'}}


class OrganizationSettingsSerializer(serializers.ModelSerializer):

    class Meta:
        model = OrganizationSettings
        fields = [
            'nickname', 'notify_message_status',
            'notify_optouts', 'external_optout_message']


class ChildOrganizationSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Organization
        fields = ['url', 'name']


class OrganizationSerializer(serializers.HyperlinkedModelSerializer):
    can_attach_files = serializers.ReadOnlyField()
    can_external_optout = serializers.ReadOnlyField()
    name = serializers.CharField(required=True)
    contact_email = serializers.EmailField(required=True)
    settings = OrganizationSettingsSerializer(required=False)
    parent = ScopedHyperLinkedRelatedField(
        required=False, allow_null=True,
        view_name='users:organization-detail',
        queryset=Organization.objects.all())
    _links = HALLinksField(
        nested_endpoints=[
            'opt_outs', 'children', 'invite_user'],
        view_name='users:organization-detail')

    class Meta:
        model = Organization
        fields = [
            'url', 'name', 'contact_email', 'settings', 'parent',
            'can_attach_files', 'can_external_optout', '_links']
        read_only_fields = ['can_attach_files', 'can_external_optout']
        extra_kwargs = {
            'url': {'view_name': 'users:organization-detail'},
            'parent': {'view_name': 'users:organization-detail'}}

    def validate(self, data):
        if not self.instance and not data.get('parent'):
            raise ValidationError({'parent': 'This field may not be blank.'})
        if self.context.get('request').user.organization != data.get('parent'):
            raise ValidationError(
                {'parent': 'Parent organization must be your organization.'})
        return super().validate(data)

    def create(self, validated_data):
        settings_data = validated_data.pop('settings', {})
        organization = Organization(**validated_data)
        organization.clean()
        organization.save()

        if settings_data:
            for field, value in settings_data.items():
                setattr(organization.settings, field, value)
            organization.settings.save()
        return organization

    def update(self, instance, validated_data):
        settings_data = validated_data.pop('settings', {})
        if settings_data:
            for field, value in settings_data.items():
                setattr(instance.settings, field, value)
            instance.settings.save()
        return super().update(instance, validated_data)


class PasswordResetInitSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(style={'input_type': 'password'})
    new_password = serializers.CharField(style={'input_type': 'password'})

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def validate_old_password(self, value):
        if self.user.check_password(value):
            return value
        raise ValidationError(
            _('Your old password is incorrect.'))


class MunchJSONWebTokenSerializer(JSONWebTokenSerializer):
    def __init__(self, *args, **kwargs):
        """ Dynamically add the USERNAME_FIELD to self.fields. """
        super().__init__(*args, **kwargs)

        self.fields[self.username_field] = serializers.CharField(
            required=False)
        self.fields['password'] = PasswordField(
            write_only=True, required=False)

    def validate(self, attrs):
        from django.contrib.auth.models import update_last_login

        username = attrs.get(self.username_field)
        password = attrs.get('password')
        # API Key authentication
        if username == 'api' and password:
            user = authenticate(secret=password)
            if user is None:
                raise AuthenticationFailed('Invalid API key')
            if not user.is_active:
                raise UserDisabledException()
            payload = rest_framework_jwt.settings.api_settings.\
                JWT_PAYLOAD_HANDLER(user)
            update_last_login(None, user)
        # Username/Password authentication
        elif all([username, password]):
            user = authenticate(username=username, password=password)
            if user:
                if not user.is_active:
                    raise UserDisabledException()

                payload = rest_framework_jwt.settings.api_settings.\
                    JWT_PAYLOAD_HANDLER(user)
                update_last_login(None, user)
            else:
                msg = _('Unable to login with provided credentials.')
                raise AuthenticationFailed(msg)
        else:
            msg = _(
                'Must include "{username_field}" and "password".')
            msg = msg.format(username_field=self.username_field)
            raise ValidationError(msg)

        return {
            'token': rest_framework_jwt.settings.api_settings.
            JWT_ENCODE_HANDLER(payload),
            'user': user}


class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MunchUser
        fields = ['identifier']

    def validate(self, attrs):
        user = MunchUser(**attrs)
        request = self.context.get('request')
        organization_id = self.context.get('organization_id')
        if not organization_id or not organization_id.isdigit() or \
                int(organization_id) not in Organization.objects.filter(
                    Q(id__in=[request.user.organization_id]) |
                    Q(parent_id=request.user.organization_id)).values_list(
                        'id', flat=True):
            raise ValidationError(_('Invalid organization.'))
        user.organization_id = self.context.get('organization_id')
        user.clean()
        return attrs
