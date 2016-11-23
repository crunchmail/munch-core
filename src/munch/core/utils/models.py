from django.db import models
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _

from .managers import OwnedModelQuerySet
from .managers import OptionallyOwnedModelQuerySet


class OwnedModelMixin:
    """ Defines the relationship to an owner and an author

    Inheriting model should define two attributes in django queryset format.

    * `owner_path` points to a users.models.Organization
    * `author_path` points to a users.models.MunchUser

    Examples:
      * `owner_path='foo'` states that the owner is in self.foo
      * `owner_path='foo__bar'` states that the owner is in self.foo.bar
      * `owner_path='self'` states that the owner is the object itself


    If you want to add the extra permissions
        (related to author and organization),
    you have to explicitly inherit metaclass.

    Example usage:

        class SomeClass(models.Model, OwnedModelMixin):
            class Meta(OwnedModelMixin.Meta):
                pass

    """
    # owner_path = 'foo__bar'

    # just a way to mark that there is no path to author
    IRRELEVANT = 'irrelevant'

    class Meta:
        default_permissions = (
            'view', 'add', 'change', 'delete',
            'view_mine', 'change_mine', 'delete_mine',
            'view_organizations', 'change_organizations',
            'delete_organizations')

    def __init__(self, *args, **kwargs):
        if not hasattr(self, 'owner_path'):
            raise NotImplementedError(
                ('{}, as a OwnedModelMixin implementor, should define a' +
                    ' "owner_path" attribute').format(self.__class__))

    @classmethod
    def defines_author(cls):
        return cls.author_path != cls.IRRELEVANT

    def get_owner(self):
        """
        :rtype Organization:
        """
        o = self

        if self.owner_path != 'self':
            for i in self.owner_path.split('__'):
                o = getattr(o, i)
        return o

    def get_author(self):
        """
        :rtype MunchUser:
        """
        o = self

        if self.author_path != 'self' and self.author_path != self.IRRELEVANT:
            for i in self.author_path.split('__'):
                o = getattr(o, i)
        return o

    @classmethod
    def has_owner_direct_link(cls):
        return not ('__' in cls.owner_path) and (cls.owner_path != 'self')

    @classmethod
    def has_author_direct_link(cls):
        return not ('__' in cls.author_path) and (cls.author_path != 'self')

    @classmethod
    def is_author_class(cls):
        return cls.author_path == 'self'

    @classmethod
    def is_owner_class(cls):
        return cls.owner_path == 'self'

    @staticmethod
    def resolve_serializer_path(serializer_data, path):
        """ Given a django queryset filter, get the object following relations,
        starting from a serializer, not an instance

        ex:
        resolve_path(o, 'foo__bar') will fetch o['foo'].bar
        resolve_path(o, 'self') will fetch o
        """
        if path == 'self':
            raise ValueError('Cannot resolve "self"')
        else:
            path_bits = path.split('__')
            # first level of relation is dict-like (nb: it's a serializer)
            o = serializer_data[path_bits[0]]
            # following levers is normal model attributes traversing
            for path_bit in path_bits[1:]:
                o = getattr(o, path_bit)
        return o

    @classmethod
    def get_directly_linked_obj(cls, serializer_data):
        """
        In case there is a relation chain to author, gets the closest instance
        to the author in the chain.

        ex: if called with data of a mail and we have the Mail-Message-User
        chain, returns the message instance.
        """
        if cls.has_author_direct_link() or cls.is_author_class():
            raise ValueError(
                'the author has direct link to this class or is this class')
        else:
            path_bits = cls.author_path.split('__')
            # first level of relation is dict-like (nb: it's a serializer)
            o = serializer_data[path_bits[0]]
            # following levers is normal model attributes traversing
            for path_bit in path_bits[1:-1]:
                o = getattr(o, path_bit)
        return o


class OptionnallyOwnedModelMixin(OwnedModelMixin):
    """ A special case of OwnedModelMixin, where ownership of an object is
    optionnal. The queryset should return owned objects and orphans.
    """

    @classmethod
    def owned_qs(cls, qs, owner):
        if cls.owner_path == 'self':
            return qs.filter(Q(pk=owner.pk) | Q(pk__isnull=True))
        else:
            return qs.filter(
                Q(**{cls.owner_path: owner}) | Q(
                    **{cls.owner_path + '__isnull': True}))

    def is_public(self):
        return self.get_author() is None or self.get_owner() is None

    # for admin interface
    is_public.boolean = True
    is_public.short_description = _('public')


class AbstractOwnedModel(models.Model, OwnedModelMixin):
    class Meta(OwnedModelMixin.Meta):
        abstract = True

    objects = OwnedModelQuerySet.as_manager()


class AbstractOptionnallyOwnedModel(models.Model, OptionnallyOwnedModelMixin):
    class Meta(OptionnallyOwnedModelMixin.Meta):
        abstract = True

    objects = OptionallyOwnedModelQuerySet.as_manager()
