import math
from collections import OrderedDict

from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination


class CountedPageNumberPagination(PageNumberPagination):
    """ Simple page pagination indicating the total numbre of pages.
    """
    UNPAGINATED_HARD_LIMIT = 2000000

    page_size = 50
    max_page_size = 1000
    page_size_query_param = 'page_size'

    def get_page_count(self):
        return math.ceil(
            self.page.paginator.count / self.get_page_size(self.request))

    def get_page_size(self, request):
        skip_pagination = getattr(
            request.accepted_renderer, 'skip_pagination', False)
        if skip_pagination:
            return self.UNPAGINATED_HARD_LIMIT
        else:
            return super().get_page_size(request)

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_count', self.get_page_count()),
            ('results', data)]))
