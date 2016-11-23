from django.conf import settings
from django.db import connection
from django.db import transaction
from rest_framework import fields
from rest_framework import serializers
from rest_framework.settings import api_settings
from rest_framework.serializers import ValidationError
from rest_framework.serializers import DjangoValidationError
from rest_framework.serializers import get_validation_error_detail

from munch.core.utils.serializers import HALLinksField
from munch.core.utils.serializers import SizeLimitedListSerializer
from munch.core.utils.relations import ScopedHyperLinkedRelatedField

from ...models import Contact
from ...models import ContactList
from ...models import ContactQueue
from ...models import CollectedContact
from ...models import ContactListPolicy
from ...models import ContactQueuePolicyAttribution
from ...validators import properties_schema_validator
from .permissions import ContactListMergePermission


class QueuePolicySerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = ContactListPolicy
        fields = ['url', 'name', ]
        read_only_fields = ['url']
        extra_kwargs = {
            'url': {'view_name': 'contacts:contactlistpolicy-detail'}}


class ContactQueueSerializer(serializers.HyperlinkedModelSerializer):
    policies = serializers.HyperlinkedRelatedField(
        many=True, view_name='contacts:contactlistpolicy-detail',
        queryset=ContactListPolicy.objects)
    _links = HALLinksField(
        nested_endpoints=['consume'],
        view_name='contacts:contactqueue-detail')
    subscription = serializers.ReadOnlyField()
    contact_fields = serializers.ListField(
        child=serializers.DictField(), required=False,
        validators=[properties_schema_validator])

    class Meta:
        model = ContactQueue
        fields = [
            'url', 'policies', 'properties', 'contact_fields',
            'contacts_count', '_links', 'subscription']
        read_only_fields = ['url', 'contacts_count', '_links', 'subscription']
        extra_kwargs = {'url': {'view_name': 'contacts:contactqueue-detail'}}

    def create(self, validated_data):
        with transaction.atomic():
            data = {k: v for k, v in validated_data.items() if k not in
                    ('policies',)}
            queue = ContactQueue(**data)
            queue.save()
            for policy in validated_data['policies']:
                pa = ContactQueuePolicyAttribution(
                    contact_queue=queue, policy=policy)
                pa.save()
            return queue

    def update(self, instance, validated_data):
        with transaction.atomic():
            for k, v in validated_data.items():
                if k != 'policies':
                    setattr(instance, k, v)
            instance.save()

            # handle the through model, not that easy, see
            # https://docs.djangoproject.com/en/dev/topics/db/models/#intermediary-manytomany
            instance.policies.clear()
            for policy in validated_data['policies']:
                ContactQueuePolicyAttribution.objects.create(
                    contact_queue=instance, policy=policy)
            return instance

    def validate_contact_fields(self, value):
        ContactFieldsFieldHelper.validate(
            self.instance, value, reverse='collected_contacts')
        return value


class CollectedContactSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = CollectedContact
        fields = ['address', 'properties', 'creation_date', 'update_date']

    def to_representation(self, obj):
        data = super().to_representation(obj)
        data['properties'] = PropertiesFieldHelper.to_representation(
            obj, reverse="contact_queue")
        return data

    def to_internal_value(self, data):
        obj = super().to_internal_value(data)
        try:
            obj['properties'] = PropertiesFieldHelper.to_internal_value(
                obj, reverse="contact_queue")
        except ValidationError as err:
            raise ValidationError({'properties': err.detail})

        return obj


class ContactQueueDetailSerializer(serializers.HyperlinkedModelSerializer):
    policies = QueuePolicySerializer(many=True, read_only=True)
    contacts = CollectedContactSerializer(many=True, read_only=True)

    class Meta:
        model = ContactQueue
        fields = [
            'url', 'policies', 'properties', 'contacts_count', 'contacts']
        read_only_fields = [
            'url', 'policies', 'properties', 'contacts_count', 'contacts']
        extra_kwargs = {'url': {'view_name': 'contacts:contactqueue-detail'}}


class URLRelatedDefault:
    """ Fills a field from the request URL
    """
    def __init__(self, url_pk, target_model, *args, **kwargs):
        self.url_pk = url_pk
        self.target_model = target_model

    def set_context(self, serializer_field):
        kwargs = serializer_field.context['kwargs']
        self.related_obj = self.target_model.objects.get(
            pk=kwargs[self.url_pk])

    def __call__(self):
        return self.related_obj


class ContactListSerializer(serializers.HyperlinkedModelSerializer):
    _links = HALLinksField(
        nested_endpoints=['contacts', 'merge'],
        view_name='contacts:contactlist-detail')

    # need to include it here so that unique_together in checked and handled
    # properly with a 400 error
    author = serializers.HiddenField(default=serializers.CreateOnlyDefault(
        serializers.CurrentUserDefault()))
    contact_fields = serializers.ListField(
        child=serializers.DictField(), required=False,
        validators=[properties_schema_validator])
    subscription = serializers.ReadOnlyField()

    class Meta:
        model = ContactList
        fields = [
            'url', 'name', 'contact_fields', 'properties',
            'source_type', 'source_ref', 'subscription',
            'contacts_count', '_links', 'author']
        read_only_fields = ['url', 'contacts_count', 'author']
        extra_kwargs = {'url': {'view_name': 'contacts:contactlist-detail'}}

    def validate_contact_fields(self, value):
        ContactFieldsFieldHelper.validate(self.instance, value)
        return value


class ContactBulkSerializer(SizeLimitedListSerializer):
    class Meta:
        # make it lazy, otherwise, overrided settings value can be missed
        max_items = lambda: settings.CONTACTS['MAX_BULK_CONTACTS']

    def create(self, validated_data):
        contacts = [Contact(**item) for item in validated_data]
        return Contact.objects.bulk_create(contacts, batch_size=30000)

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

        ret = []
        errors = {
            'validation_errors': {},
            'no_address': 0,
            'duplicates': []
        }
        unique_couples = set()

        for item in data:
            try:
                validated = self.child.run_validation(item)
            except ValidationError as exc:
                if not item.get('address'):
                    errors['no_address'] += 1
                else:
                    errors['validation_errors'][
                        item.get('address')] = exc.detail
            else:
                unicity = (validated['contact_list'], validated['address'])
                if unicity not in unique_couples:
                    ret.append(validated)
                    unique_couples.add(unicity)
                else:
                    errors['duplicates'].append(item.get('address'))

        if any(v for v in errors.values()):
            return ret, ValidationError(errors)

        return ret, ValidationError({})

    def is_partly_invalid(self):
        """ Allows to have a multiple serializer (many=True) with part of the
            raise serializers data valid and part of the data invalid.
        """
        assert hasattr(self, 'initial_data'), (
            'Cannot call `.is_partly_valid()`no `data=` keyword argument was'
            'passed when instantiating the serializer instance.'
        )
        has_errors = False

        # this one may trigger a ValidationError up to http client
        self.run_list_size_validation(self.initial_data)

        # those can't, from here, validation is always considered good
        if not hasattr(self, '_validated_data'):
            self._validated_data, exc = self.run_partial_validation(
                self.initial_data)
            self._partial_errors = exc.detail
            if exc.detail:
                has_errors = True

        # partly valid if at least something is valid
        return has_errors

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
        value, error = self.to_internal_value_error(data)
        try:
            self.run_validators(value)  # does nothing in our case
            value = self.validate(value)
            assert value is not None, \
                '.validate() should return the validated data'
        except (ValidationError, DjangoValidationError) as exc:
            raise ValidationError(detail=get_validation_error_detail(exc))
        return value, error


class ContactFieldsFieldHelper:
    @classmethod
    def validate(cls, instance, new_contact_fields, reverse='contacts'):
        errors = {}
        # Create reversed contact_fields like that:
        # {
        #  "Age": {"type": "Integer", "required": True},
        #  "Firstname": {"type": "Char", "required": True}
        # }

        # Raise error if new field have same name than another
        _duplicates = {}
        for field in new_contact_fields:
            field = field['name'].strip().lower()
            if field not in _duplicates:
                _duplicates[field] = 0
            _duplicates[field] += 1
        for field, count in _duplicates.items():
            if count > 1:
                if not errors.get(field):
                    errors[field] = []
                errors[field].append(
                    "can't add same field multiple times (case insensitive)")
        del _duplicates

        reversed_initial = {}
        # Check if instance a new one or an update
        if hasattr(instance, 'pk'):
            reversed_initial = {
                field.get('name'): {
                    'type': field.get('type'),
                    'required': field.get('required', False)}
                for field in instance.contact_fields}
        reversed_new = {
            field.get('name').strip().lower(): {
                'type': field.get('type'),
                'required': field.get('required', False)}
            for field in new_contact_fields}
        for field_name, field in reversed_new.items():
            if not errors.get(field_name):
                errors[field_name] = []
            field_type = field.get('type')

            # Raise error if new field have same name than another
            lowered_fields = [f.lower() for f in list(reversed_new)]
            if field_name.lower() in [
                    x for x in list(reversed_new)
                    if lowered_fields.count(x.lower()) > 1]:
                errors[field_name].append(
                    "can't add same field multiple times (case insensitive)")
                continue

            # Do not check field "updates" if it's a new Contact(Queue/List)
            if not instance:
                continue

            # Raise error if new field is required and there are contacts
            if field_name not in reversed_initial and field.get('required'):
                if getattr(instance, reverse).all().count():
                    errors[field_name].append("can't add field as required")
                    continue
            # Check if initial field has been updated
            if field_name in reversed_initial:
                initial_field = reversed_initial.get(field_name)
                # Raise error if existing field has changed its type
                if initial_field.get('type') != field_type:
                    # If new type is not Char we must raise an error
                    if field_type != "Char":
                        errors[field_name].append(
                            "can't change existing field type to %s"
                            % field_type)
                # Raise error if existing field setted as required
                if not initial_field.get('required') and field.get('required'):
                    _filter = {'properties__%s__isnull' % field_name: True}
                    # Check if it's possible to set existing field as required
                    # by checking if every contacts field is not empty
                    if getattr(instance, reverse).filter(**_filter).exists():
                        errors[field_name].append(
                            "can't set existing field as required")
                        continue
            # Iterate over removed fields
            removed_fields = reversed_initial.keys() - reversed_new.keys()
            # Clean all contacts properties if there are removed fields
            if removed_fields:
                db_table = getattr(instance, reverse).model._meta.db_table
                contact_ids = getattr(instance, reverse).values_list(
                    "pk", flat=True)
                # Run cleaning only if there are contacts attached
                if contact_ids:
                    cursor = connection.cursor()
                    # Need to format just db_table alone because parametrized
                    # statements seems to be only for "values" and not table
                    # names. See: http://stackoverflow.com/a/9354420
                    # This raw SQL statement use Postgres `delete` method to
                    # manipulate hstore that we can do that with Django.
                    cursor.execute(("""
                        UPDATE {db_table}
                        SET properties = delete(properties, %s)
                        WHERE id in %s""".format(db_table=db_table)), [
                        list(removed_fields), tuple(contact_ids)])

        if any([error for error in errors.values()]):
            raise ValidationError({k: v for k, v in errors.items() if v})

        return new_contact_fields


class PropertiesFieldHelper:
    @classmethod
    def get_field_serializer(cls, field_type):
        try:
            # Try to retrieve right field type
            serializer = getattr(serializers, '%sField' % field_type)
        except AttributeError:
            # Fallback on CharField
            serializer = serializers.CharField
        return serializer

    @classmethod
    def to_representation(cls, instance, reverse="contact_list"):
        serialized_properties = {}
        properties = instance.properties
        # Iterate over Contact.list.contact_fields
        for field in getattr(instance, reverse).contact_fields:
            field_name, field_type = field.get('name'), field.get('type')
            field_value = properties.get(field_name)
            # If field is empty and not required let's ignore it
            if not field_value and not field.get('required'):
                continue
            field_serializer = cls.get_field_serializer(field_type)()
            try:
                serialized_properties[field_name] = field_serializer\
                    .to_representation(
                        field_serializer.to_internal_value(field_value))
            except (TypeError, ValueError, ValidationError) as err:
                # If we go here it's because we validate a field in
                # `to_internal_value` that we are unable to representate.
                # Which is not a good point.
                errors = ['Error while rendering field value']
                if isinstance(err, ValidationError):
                    errors += err.detail
                else:
                    errors.append(str(err))
                raise Exception({field_name: errors})
        return serialized_properties

    @classmethod
    def to_internal_value(cls, data, reverse="contact_list"):
        """
            reverse parameter is attribut to
            retrieve: ContactList or ContactQueue
        """
        errors = {}
        returned_properties = {}
        properties = data.get('properties')
        # Iterate over Contact.list.contact_fields
        for field in data.get(reverse).contact_fields:
            field_name, field_type = field.get('name'), field.get('type')
            field_value = properties.get(field_name)
            errors[field_name] = []
            # If field is empty and required, raise an error and continue
            if not field_value and field.get('required'):
                errors[field_name].append('is required')
                continue
            # If field is empty and not required let's ignore it
            if not field_value and not field.get('required'):
                continue
            field_serializer = cls.get_field_serializer(field_type)()
            try:
                field_serializer.to_internal_value(field_value)
                returned_properties[field_name] = field_value
            except (TypeError, ValueError) as err:
                errors[field_name] += err
            except ValidationError as err:
                errors[field_name] += err.detail

        if any([error for error in errors.values()]):
            raise ValidationError(errors)

        return returned_properties


class ContactSerializer(serializers.HyperlinkedModelSerializer):
    contact_list = serializers.HyperlinkedRelatedField(
        view_name='contacts:contactlist-detail',
        queryset=ContactList.objects.all())

    class Meta:
        model = Contact
        fields = [
            'url', 'contact_list', 'address', 'properties',
            'creation_date', 'update_date']
        read_only_fields = ['url', 'creation_date', 'update_date']
        list_serializer_class = ContactBulkSerializer
        extra_kwargs = {'url': {'view_name': 'contacts:contact-detail'}}

    def to_representation(self, obj):
        data = super().to_representation(obj)
        data['properties'] = PropertiesFieldHelper.to_representation(obj)
        return data

    def to_internal_value(self, data):
        obj = super().to_internal_value(data)
        try:
            obj['properties'] = PropertiesFieldHelper.to_internal_value(obj)
        except ValidationError as err:
            raise ValidationError({'properties': err.detail})

        return obj


class NestedContactSerializer(ContactSerializer):
    """ A ContactSerializer which list info comes from context (url)

    ... and not from input (api-submited body)
    """

    contact_list = serializers.HiddenField(
        default=serializers.CreateOnlyDefault(
            URLRelatedDefault('contact_list_pk', ContactList)))

    @classmethod
    def nest_properties(cls, data):
        """ Stick every unknown provided field into the "properties" hash

        >>> NestedContactSerializer.nest_properties(
        ... {'address': 'a@example.com','a':'b'}) == \
            {'properties': {'a': 'b'}, 'address': 'a@example.com'}
        True
        """
        nested_data = {'properties': {}}
        for k, v in data.items():
            if k in cls.Meta.fields:
                nested_data[k] = v
            else:
                sub_k = k.split('properties.')[-1]
                nested_data['properties'][sub_k] = v
        return nested_data

    def filter_properties(self, properties):
        # keep only the properties specified in fields url kwarg
        request = self.context['request']
        try:
            fields = request.query_params['fields']
        except KeyError:
            return properties
        else:
            return {k: v for k, v in properties.items() if k in fields}

    def to_internal_value(self, data):
        nested_data = self.nest_properties(data)
        nested_data['properties'] = self.filter_properties(
            nested_data['properties'])
        return super().to_internal_value(nested_data)


class ContactListListSerializer(serializers.Serializer):
    """ Used for list merge
    """
    contact_lists = ScopedHyperLinkedRelatedField(
        many=True,
        queryset=ContactList.objects.all(),  # FIXME,
        view_name='contacts:contactlist-detail',
        default=[])

    def __init__(self, master_list, *args, **kwargs):
        """
        :param master_list: the list that will receive others contacts
        """
        self.master_list = master_list
        super().__init__(*args, **kwargs)

    def validate_contact_lists(self, value):
        request = self.context['request']
        perm = ContactListMergePermission()

        # check that we can delete the lists we are going to empty
        # into the master one
        for contact_list in value:
            if not perm.can_user_do(request.user, contact_list, 'delete'):
                raise ValidationError(
                    "You don't have delete rights on {}".format(contact_list))
        return value

    def validate(self, data):
        if self.master_list in data['contact_lists']:
            raise ValidationError('Cannot merge a contact list with itself')
        return data
