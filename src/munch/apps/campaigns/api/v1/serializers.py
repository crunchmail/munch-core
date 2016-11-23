from django.conf import settings
from django.utils.translation import ugettext as _
from rest_framework import serializers
from rest_framework import fields
from rest_framework.settings import api_settings
from rest_framework.serializers import ValidationError
from rest_framework.serializers import DjangoValidationError
from rest_framework.serializers import get_validation_error_detail

from munch.core.models import Category
from munch.core.utils.serializers import HALLinksField
from munch.core.utils.serializers import SizeLimitedListSerializer
from munch.core.utils.serializers import ForwardValidationErrorsMixin
from munch.core.utils.relations import ScopedHyperLinkedRelatedField

from ...fields import EmailListField
from ...validators import validate_no_virus
from ...models import Mail
from ...models import Message
from ...models import MailStatus
from ...models import MessageAttachment


class NestedTrackingSummarySerializer(serializers.Serializer):
    opened = serializers.DateTimeField(source='first_open')
    open_time = serializers.IntegerField()
    clicked = serializers.ListField(
        source='clicks', child=serializers.DictField())


class NestedMailStatusSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = MailStatus
        fields = ('status', 'creation_date', 'raw_msg')


class CachedHyperlinkedRelatedField(serializers.HyperlinkedRelatedField):
    """ HyperlinkedRelatedField but with a cache on the deserializing part

    Cache is only valid the time of the Field lifetime (usually dies with the
    request).
    """
    def __init__(self, *args, **kwargs):
        self._memoize_cache = {}
        super().__init__(*args, **kwargs)

    def get_object(self, view_name, view_args, view_kwargs):
        cache = self._memoize_cache
        key = (view_name, tuple(view_kwargs.items()))

        v = cache.get(key, None)

        if not v:
            v = super().get_object(view_name, view_args, view_kwargs)
            cache[key] = v

        # If no cached version : store and return
        return v


class CachedScopedHyperLinkedRelatedField(
        CachedHyperlinkedRelatedField,
        ScopedHyperLinkedRelatedField):
    pass


########
# Mail #
########
class MailBulkSerializer(serializers.HyperlinkedModelSerializer):
    """
    This serializer is only used to validate bulk item for MailListSerializer
    """
    message = CachedScopedHyperLinkedRelatedField(
        view_name='campaigns:message-detail',
        queryset=Message.objects.all())
    # TODO: Apiv2 rename
    to = serializers.EmailField(source='recipient')

    class Meta:
        model = Mail
        fields = ['to', 'message', 'source_type', 'source_ref', 'properties']

    def run_validation(self, data=[]):
        """
        We override the default `run_validation`, because the validation
        performed by validators and the `.validate()` method should
        be coerced into an error dictionary with a 'non_fields_error' key.
        """
        (is_empty_value, data) = self.validate_empty_values(data)
        if is_empty_value:
            return data

        try:
            value = self.to_internal_value(data)
            self.run_validators(value)
            value = self.validate(value)
            assert value is not None, '.validate() should return the validated data'  # noqa
        except (ValidationError, DjangoValidationError) as exc:
            # TODO: Must be 'recipient' instead of 'to' in v2
            raise ValidationError(
                detail={
                    'to': data['to'],
                    'errors': get_validation_error_detail(exc)})

        return value

    def get_validators(self):
        """
        Determine the set of validators to use when instantiating serializer.
        """
        # If the validators have been declared explicitly then use that.
        validators = getattr(getattr(self, 'Meta', None), 'validators', None)
        if validators is not None:
            return validators[:]

        # Otherwise use the default set of validators.
        return self.get_unique_for_date_validators()


class MailListSerializer(SizeLimitedListSerializer):
    class Meta:
        # make it lazy, otherwise, overrided settings value can be missed
        max_items = lambda: settings.CAMPAIGNS['MAX_BULK_EMAILS']

    def create(self, validated_data):
        mails = [Mail(**item) for item in validated_data]
        return Mail.objects.bulk_create(mails, batch_size=30000)

    def build_detailed_response(self):
        assert hasattr(self, 'initial_data'), (
            'Cannot call `.is_partly_valid()`no `data=` keyword argument was'
            'passed when instantiating the serializer instance.'
        )
        # this one may trigger a ValidationError up to http client
        self.run_list_size_validation(self.initial_data)

        # those can't, from here, validation is always considered good
        if not hasattr(self, '_validated_data'):
            self._validated_data, detail = self.run_partial_validation(
                self.initial_data)
            self._detailed_response = detail

    def run_partial_validation(self, data=fields.empty):
        """
        We override the default `run_validation`, because the validation
        performed by validators and the `.validate()` method should
        be coerced into an error dictionary with a 'non_fields_error' key.
        """
        # Called 1 time for all the data list
        # output of this function is set into self._validated_data by is_valid
        (is_empty_value, data) = self.validate_empty_values(data)
        if is_empty_value:
            return data
        value, detail = self.to_internal_value_error(data)
        try:
            self.run_validators(value)  # does nothing in our case
            value = self.validate(value)
            assert value is not None, \
                '.validate() should return the validated data'
        except (ValidationError, DjangoValidationError) as exc:
            raise ValidationError(detail=get_validation_error_detail(exc))
        return value, detail

    def to_internal_value_error(self, data):
        """ Returns both errors and valid data
        :returns: a couple: list of valid values
                            ValidationError with all errors
        """
        # Called 1 time for all the data list

        if fields.html.is_html_input(data):
            data = fields.html.parse_html_list(data)

        if not isinstance(data, list):
            message = self.error_messages['not_a_list'].format(
                input_type=type(data).__name__
            )
            raise ValidationError({
                api_settings.NON_FIELD_ERRORS_KEY: [message]
            })

        detail = {
            'validation_errors': {},
            'no_address': 0,
            'duplicates': [],
            'results': []
        }
        unique_couples = set()
        messages = []

        cleaned_data = []
        for item in data:
            if not isinstance(item, dict):
                detail['no_address'] += 1
                continue
            # TODO: Must be 'recipient' instead of 'to' in v2
            if not item.get('to') or not item.get('message'):
                detail['no_address'] += 1
                continue

            # TODO: Must be 'recipient' instead of 'to' in v2
            unicity = (item['message'], item['to'])
            if unicity not in unique_couples:
                unique_couples.add(unicity)
            else:
                # TODO: Must be 'recipient' instead of 'to' in v2
                detail['duplicates'].append(item['to'])
                continue

            if item['message'] not in messages:
                if len(messages) > 0:
                    detail[api_settings.NON_FIELD_ERRORS_KEY] = [
                        'Every object must have same message']
                    return [], detail
                messages.append(item['message'])

            cleaned_data.append(item)

        serializer = MailBulkSerializer(
            data=cleaned_data, many=True, context=self.context)

        if not serializer.is_valid():
            in_error, only_valid = [], []

            for error in serializer.errors:
                if error:
                    in_error.append(error['to'])
                    detail['validation_errors'][error['to']] = error['errors']

            for item in cleaned_data:
                if item['to'] not in in_error:
                    only_valid.append(item)

            serializer = MailBulkSerializer(
                data=only_valid, many=True, context=self.context)
            serializer.is_valid()

        cleaned_data = serializer.validated_data

        if cleaned_data:
            recipients = []
            results = []
            for item in cleaned_data:
                recipients.append(item['recipient'])

            recipients_to_remove = Mail.objects.filter(
                message=cleaned_data[0]['message'],
                recipient__in=recipients).values_list('recipient', flat=True)

            for item in cleaned_data:
                if item['recipient'] not in recipients_to_remove:
                    results.append(item)
                else:
                    detail['validation_errors'][item['recipient']] = [
                        _('This address is already attached to this message.')]

            cleaned_data = results

        return cleaned_data, detail


class MailBulkResultSerializer(serializers.HyperlinkedModelSerializer):
    to = serializers.EmailField(source='recipient')
    message = CachedScopedHyperLinkedRelatedField(
        view_name='campaigns:message-detail',
        queryset=Message.objects.all())
    # TODO: Apiv2 rename
    date = serializers.DateTimeField(source='creation_date', read_only=True)

    class Meta:
        model = Mail
        fields = [
            'url', 'to', 'date', 'message',
            'source_type', 'source_ref', 'properties']
        extra_kwargs = {'url': {'view_name': 'campaigns:recipient-detail'}}


class MailSerializer(serializers.HyperlinkedModelSerializer):
    last_status = NestedMailStatusSerializer(read_only=True)
    tracking = NestedTrackingSummarySerializer(
        read_only=True, source='tracking_info')
    message = CachedScopedHyperLinkedRelatedField(
        view_name='campaigns:message-detail',
        queryset=Message.objects.all())
    # TODO: Apiv2 rename
    to = serializers.EmailField(source='recipient')
    _links = HALLinksField(
        nested_endpoints=['optout', 'status_log'],
        view_name='campaigns:recipient-detail')
    # TODO: Apiv2 rename
    date = serializers.DateTimeField(source='creation_date', read_only=True)
    delivery_status = serializers.CharField(source='curstatus', read_only=True)

    class Meta:
        model = Mail
        fields = [
            'url', 'to', 'date', 'last_status', 'message', 'tracking',
            'delivery_status', 'source_type', 'source_ref', 'properties',
            '_links']
        read_only_fields = ['date', 'delivery_status']
        list_serializer_class = MailListSerializer
        extra_kwargs = {'url': {'view_name': 'campaigns:recipient-detail'}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        extra_fields = ['last_status', 'tracking']

        request = kwargs['context'].get('request')
        if request and request.method == 'GET':
            for field in request.GET.get('extra_fields', '').split(','):
                if field in extra_fields:
                    extra_fields.remove(field)
            for field in extra_fields:
                self.fields.pop(field)

    def validate_message(self, value):
        if value.status in [Message.SENDING, Message.SENT]:
            raise ValidationError(_(
                "Cannot add this recipient to a "
                "sending or already sent message."))
        return value


###########
# Message #
###########
class MessageSerializer(
        ForwardValidationErrorsMixin,
        serializers.HyperlinkedModelSerializer):
    completion_date = serializers.ReadOnlyField()
    creation_date = serializers.ReadOnlyField()
    msg_issue = serializers.ReadOnlyField()
    is_spam = serializers.ReadOnlyField()
    spam_score = serializers.ReadOnlyField()
    recipient_count = serializers.ReadOnlyField(source='mails.count')
    category = ScopedHyperLinkedRelatedField(
        view_name='core:category-detail',
        queryset=Category.objects.all(),
        required=False, allow_null=True)

    _links = HALLinksField(
        nested_endpoints=[
            'preview_send', 'preview', 'preview.html', 'preview.txt',
            'recipients', 'bounces', 'opt_outs', 'stats', 'attachments'],
        endpoints={'archive_url': {
            'view_name': 'message_web_view',
            'lookup_field': 'identifier',
            'lookup_key': 'identifier'}},
        view_name='campaigns:message-detail')

    def validate(self, attrs):
        """
        http://www.django-rest-framework.org/topics/3.0-announcement/#differences-between-modelserializer-validation-and-modelform
        """
        request = self.context.get('request', None)
        # Re-use model validation logic
        instance = Message(author=request.user, **attrs)
        try:
            instance.clean()
            if 'html' in attrs:
                instance.validate_html()
        except DjangoValidationError as err:
            message = {}
            for field, errors in err.message_dict.items():
                if not isinstance(errors, list):
                    errors = [errors]
                message[field] = errors
            raise ValidationError(message)
        return attrs

    class Meta:
        model = Message
        read_only_fields = ['send_date']
        fields = (
            'url', 'id', 'name', 'sender_email', 'sender_name', 'subject',
            'html', 'status', 'category', 'recipient_count', 'properties',
            'creation_date', 'send_date', 'completion_date', 'track_open',
            'track_clicks', 'external_optout', 'detach_images', 'spam_score',
            'spam_details', 'is_spam', 'msg_issue', '_links', )
        extra_kwargs = {'url': {'view_name': 'campaigns:message-detail'}}


class MailStatusSerializer(serializers.HyperlinkedModelSerializer):
    address = serializers.ReadOnlyField(source='mail.recipient')

    class Meta:
        model = MailStatus
        fields = ('status', 'creation_date', 'raw_msg', 'address')


class MessageAttachmentSerializer(serializers.HyperlinkedModelSerializer):
    file = serializers.FileField(
        validators=[validate_no_virus], write_only=True)

    _links = HALLinksField(
        nested_endpoints=['download', 'content'],
        view_name='campaigns:messageattachment-detail')

    def validate(self, attrs):
        # this is defined as a pre_save because cant be checked in clean() as
        # there is not yet instance.message at this step.
        same_named = attrs['message'].attachments.filter(
            file__endswith='/{}'.format(attrs['file'].name))
        if same_named.exists():
            raise ValidationError((
                'A file with the same name already exists '
                'for this message : {}').format(same_named.first()))

        # Now check whether we would fit within the total allowed
        # attachment size for the message
        total_size = 0
        for attachment in attrs['message'].attachments.all():
            total_size += attachment.size
        total_size += attrs['file'].size
        if total_size > settings.CAMPAIGNS['ATTACHMENT_TOTAL_MAX_SIZE']:
            raise ValidationError(_(
                'Can not accept this file. Total attachment size for this '
                'message ({} bytes) would exceed the maximum allowed size of '
                '{} bytes'.format(
                    total_size, settings.CAMPAIGNS[
                        'ATTACHMENT_TOTAL_MAX_SIZE'])))
        return attrs

    def validate_file(self, value):
        # Check this attachment's size to make sure it's not too big
        if value.size > settings.CAMPAIGNS['ATTACHMENT_MAX_SIZE']:
            raise ValidationError(_(
                'This file is too big. Maximum allowed size is '
                '{} bytes'.format(settings.CAMPAIGNS['ATTACHMENT_MAX_SIZE'])))
        if len(value.name) > 100:
            raise ValidationError(_(
                'This file name is too long. It must be under 100 characters'))
        return value

    def create(self, validated_data):
        validated_data.update({'original_name': validated_data['file'].name})
        return super().create(validated_data)

    class Meta:
        model = MessageAttachment
        fields = (
            'url', 'message', 'file', 'filename', 'size', 'size_in_mail',
            '_links')
        readonly_fields = ('filename', 'size', 'size_in_mail')
        extra_kwargs = {
            'url': {'view_name': 'campaigns:messageattachment-detail'},
            'message': {'view_name': 'campaigns:message-detail'}}


class EmailListSerializer(serializers.CharField):
    """ Serializer for comma-separated emails in a string

    Re-use EmailListField logic.
    """
    default_validators = [EmailListField.EmailListValidator()]

    def to_representation(self, obj):
        f = EmailListField()
        char_obj = super().to_representation(obj)
        return f.value_to_string(char_obj)

    def to_internal_value(self, data):
        f = EmailListField()
        char_str = super().to_internal_value(data)
        return f.to_python(char_str)


class PreviewRecipientsSerializer(serializers.Serializer):
    to = EmailListSerializer(source='recipient')
