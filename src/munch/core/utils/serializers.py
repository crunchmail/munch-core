import urllib
from collections import OrderedDict

from rest_framework import relations
from rest_framework import serializers
from rest_framework.compat import unicode_to_repr
from rest_framework.fields import empty
from rest_framework.reverse import reverse
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.serializers import ValidationError as DRFValidationError


class HALLinksField(relations.HyperlinkedIdentityField):
    """ Tries to represent related links a HAL-compliant way.

    Offer special support for nested links.

      Ex: /foo/:n/info/ is a nested link of /foo/:n/

    See http://stateless.co/hal_specification.html
    """
    def __init__(self, endpoints={}, nested_endpoints=[], *args, **kwargs):
        """
        :param endpoints: dict of reversable urls to point to other API
                          resources, `link_name` will be used as key for the
                          URL in the resource.
        :type endpoints: dict {<link_name> {"lookup_key": str,
                               "lookup_field": str,
                               "view_name": str}
        :param nested_endpoints: list of url suffixes leading to nested
                                 operations on the resource
                                 (ex: ['preview', 'check'])
        """
        self.nested_endpoints = nested_endpoints
        self.endpoints = endpoints

        for d in endpoints.values():
            assert d.keys() == set(
                ['lookup_key', 'lookup_field', 'view_name']), (
                    "bad endpoint format keys set : {}".format(d.keys()))
        super().__init__(*args, **kwargs)

    def get_attribute(self, obj):
        return obj

    def to_representation(self, value):
        links = OrderedDict()
        prefix = super().to_representation(self.get_attribute(value))
        for i in self.nested_endpoints:
            # We consider if it contains a dot its a content-type indication,
            # so no trailing slash
            if '.' in i:
                suffix = ''
            else:
                suffix = '/'
            links[i] = {'href': urllib.parse.urljoin(prefix, i) + suffix}

        # Reverse all the URL for endpoints, using targeted object
        request = self.context.get('request', None)
        for url_name, url_lookup in self.endpoints.items():
            lookup_value = getattr(value, url_lookup['lookup_field'])
            links[url_name] = {
                'href':
                    reverse(
                        url_lookup['view_name'],
                        kwargs={url_lookup['lookup_key']: lookup_value},
                        request=request)}
        return links


class SizeLimitedListSerializer(serializers.ListSerializer):
    DEFAULT_MAX_ITEMS = 10000

    def run_list_size_validation(self, data):
        try:
            max_items = self.Meta.max_items()
        except AttributeError:
            max_items = self.DEFAULT_MAX_ITEMS

        items_count = len(data)

        if items_count > max_items:
            raise serializers.ValidationError(detail={'non_field_errors': [
                'Serializer limited to {} items at once, got {}'.format(
                    max_items, items_count)]})

    def run_validation(self, data=empty):
        """
        Natural place for this validation to occur would be in self.validate()
        but it's not a safe option as we would validate *all* items *before*
        rejecting.

        Overloading run_validation allows to raise ValidationError earlier.
        """
        self.run_list_size_validation(data)
        return super().run_validation(data)

    # Those two are bugfix for DRF bulk:
    # https://github.com/miki725/django-rest-framework-bulk/issues/33
    def __iter__(self):
        return self

    def __next__(self):
        raise StopIteration


class CurrentOrganizationDefault(object):
    """ Class inspired by rest_framework.serializers.CurrentUserDefault
    """
    def set_context(self, serializer_field):
        request = serializer_field.context['request']
        if request.user.is_authenticated():
            self.organization = request.user.organization
        else:
            self.organization = None

    def __call__(self):
        return self.organization

    def __repr__(self):
        return unicode_to_repr('%s()' % self.__class__.__name__)


class ForwardValidationErrorsMixin:
    """ Allows to forward django validation errors as DRF validation errors,
    on save
    """
    def create(self, validated_data, *args, **kwargs):
        try:
            return super().create(validated_data, *args, **kwargs)
        except DjangoValidationError as e:
            raise DRFValidationError(e.error_list)

    def update(self, instance, validated_data, *args, **kwargs):
        try:
            return super().update(instance, validated_data, *args, **kwargs)
        except DjangoValidationError as e:
            raise DRFValidationError(e.error_list)
