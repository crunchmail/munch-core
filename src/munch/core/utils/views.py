from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.generics import get_object_or_404
from rest_framework.serializers import ValidationError as DRFValidationError

from .api import get_subroute_method
from .permissions import MunchResourcePermission
from .pagination import CountedPageNumberPagination


class classproperty(property):
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()


class OrganizationOwnedViewSetMixin:
    """ Auto-handle a "organization" field according to the current User

    Supposed to be used with utils.OwnedModelMixin models.
    """

    @classmethod
    def mk_permission_classes(cls, extra_perms=[]):
        """ Dynamically build permission classes

        based on underlying model
        """
        return [MunchResourcePermission.mk_class(cls.model)] + extra_perms

    @classproperty
    @classmethod
    def permission_classes(cls):
        return cls.mk_permission_classes()

    @classmethod
    def _get_owner_permission(cls):
        for i in cls.permission_classes:
            if issubclass(i, MunchResourcePermission):
                return i()

        raise ValueError(
            'That view should use a MunchResourcePermission class')

    def get_object(self):
        """ That override is to get 403 instead of 404 on single object ops

        Mostly a copy-paste from GenericAPIView
        """
        queryset = self.filter_queryset(self.model.objects.all())
        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        assert lookup_url_kwarg in self.kwargs, (
            'Expected view %s to be called with a URL keyword argument '
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            'attribute on the view correctly.' %
            (self.__class__.__name__, lookup_url_kwarg))
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        # May raise a permission denied
        self.check_object_permissions(self.request, obj)
        return obj

    def get_queryset(self):
        perm = self._get_owner_permission()
        qs = perm.filter_queryset(
            self.model.objects.all(), self.request)

        if hasattr(self, 'ordering'):
            return qs.order_by(self.ordering)
        return qs

    def _auto_set_owner_author(self):
        kwargs = {}
        if self.model.has_owner_direct_link():
            kwargs[self.model.owner_path] = self.request.user.organization
        if self.model.has_author_direct_link() and self.model.defines_author():
            kwargs[self.model.author_path] = self.request.user
        return kwargs

    def _check_author_link_permissions(self, serializer_row):
        """ Checks if legitimate to link to a resource

        We consider that legitimacy comes from having right to edit the
        resource we link to.
        """
        if (not self.model.has_author_direct_link() and
                not self.model.is_author_class()):
            referent_obj = self.model.get_directly_linked_obj(serializer_row)
            perm = self._get_owner_permission()
            if not perm.can_user_do(self.request.user, referent_obj, 'change'):
                raise DRFValidationError(
                    'You tried to link to a forbidden resource : {}'.format(
                        referent_obj))

    def perform_create(self, serializer):
        kwargs = self._auto_set_owner_author()
        if getattr(serializer, 'many', False):
            serializer_data_rows = serializer.validated_data
        else:
            serializer_data_rows = [serializer.validated_data]

        for row in serializer_data_rows:
            self._check_author_link_permissions(row)

        serializer.save(**kwargs)

    def perform_update(self, serializer):
        # treatement is strictly similar
        return self.perform_create(serializer)


class OrganizationOptionnallyOwnedViewSetMixin(OrganizationOwnedViewSetMixin):
    pass


class MunchModelViewSetMixin:
    def get_view_description(self, html=False):
        """
        Return some descriptive text for the view, as used in OPTIONS responses
        and in the browsable API.
        """
        func = self.settings.VIEW_DESCRIPTION_FUNCTION
        return func(self.__class__, html, instance=self)

    def filter_queryset(self, queryset):
        """
        If we are in a list_route or detail_route, just pass through
        """
        if not get_subroute_method(self):
            for backend in list(self.filter_backends):
                queryset = backend().filter_queryset(
                    self.request, queryset, self)
        return queryset


class NestedViewMixin:
    def get_parent_object(self, pk):
        parent_obj = get_object_or_404(self.parent_model, pk=pk)
        self.check_object_permissions(self.request, parent_obj)
        return parent_obj

    def get_serializer(self, *args, **kwargs):
        """ Directly inspired from DRF GenericAPIView
        """
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    def get_serializer_class(self):
        return self.serializer_class

    def get_serializer_context(self):
        return {'request': self.request}


class NestedView(NestedViewMixin, APIView):
    """ View meant to be nested within a resource

    It uses explicit url conf rather than router

    must define a `parent_model`
    may define a `serializer_class`

    Checks permissions on the parent object
    """
    serializer_class = serializers.Serializer


def paginated_response(queryset, serializer_class, request):
    """
    Pagination helper for a @detail route.
    http://stackoverflow.com/a/29144786/1377500

    :type serializer_class: rest_framework.serializers.Serializer
    :rtype:                 rest_framework.response.Response
    """
    paginator = CountedPageNumberPagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(
        page, many=True, context={'request': request})
    return paginator.get_paginated_response(serializer.data)


def filtered_qs(qs, filter_class, request):
    """ Apply a django-filter to a queryset against a request

    :type qs:           django.db.models.QuerySet
    :type filter_class: django_filters.FilterSet
    :return:            filtered queryset
    """
    return filter_class(request.query_params, queryset=qs).qs


def paginated(serializer_class):
    """ Decorator to transform a queryset return into a Paginated response.
    """
    def wrap(f):
        def wrapped_f(self, request, *args, **kwargs):
            qs = f(self, request, *args, **kwargs)
            return paginated_response(qs, serializer_class, request)
        # Preserve the attributes of original function
        for i in dir(f):
            if not i.startswith('_'):
                setattr(wrapped_f, i, getattr(f, i))
        return wrapped_f
    return wrap


def filtered(filter_class):
    """ Decorator to filter a queryset, keeping a queryset as return val
    """
    def wrap(f):
        def wrapped_f(self, request, *args, **kwargs):
            qs = f(self, request, *args, **kwargs)
            return filtered_qs(qs, filter_class, request)
        wrapped_f.filter_class = filter_class
        return wrapped_f
    return wrap
