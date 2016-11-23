import datetime

from django.db import models
from django.db.models import Q
from django.db.models import Sum


class MedianQuerySetMixin:
    def median(self, field, order=True):
        """ Returns the median field value of a given field

        :param order: should we order the queryset before picking the median ?
                      generally you want it on except for some subtle
                      situations with SQL.

        If the set is empty, returns 0
        """
        qs = self.exclude(**{field + "__isnull": True})
        count = qs.count()

        if not count:
            return datetime.timedelta()

        result = qs.aggregate(
            Sum(field)).get('{}__sum'.format(field)).total_seconds()
        return datetime.timedelta(seconds=int(result / count))


class OwnedModelQuerySet(models.QuerySet):
    def author_query(self, author):
        if self.model.author_path == 'self':
            return Q(pk=author.pk)
        return Q(**{self.model.author_path: author})

    def owner_query(self, owner):
        if self.model.owner_path == 'self':
            return Q(pk=owner.pk)
        return Q(**{self.model.owner_path: owner})

    def orphan_query(self):
        return Q(**{self.model.owner_path: None})

    def from_author(self, author, or_orphan=False):
        """
        :type author: MunchUser
        """
        if or_orphan:
            return self.filter(self.author_query(author) | self.orphan_query())
        return self.filter(self.author_query(author))

    def from_owner(self, owner, or_orphan=False):
        """
        :type owner: Organization
        """
        q = self.owner_query(owner)
        if or_orphan:
            return self.filter(q | self.orphan_query())
        return self.filter(q)


class OptionallyOwnedModelQuerySet(OwnedModelQuerySet):
    def from_author(self, author, or_orphan=True):
        return super().from_author(author, or_orphan)

    def from_owner(self, owner, or_orphan=True):
        return super().from_owner(owner, or_orphan)
