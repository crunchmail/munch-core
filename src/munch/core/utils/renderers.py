import json

from rest_framework import renderers
from rest_framework_csv.renderers import CSVRenderer


class PlainTextRenderer(renderers.BaseRenderer):
    media_type = 'text/plain'
    format = 'txt'

    def render(self, data, media_type=None, renderer_context=None):
        return str(data).encode(self.charset)


class HTMLRenderer(renderers.BaseRenderer):
    media_type = 'text/html'
    format = 'html'

    def render(self, data, media_type=None, renderer_context=None):
        return str(data).encode(self.charset)


class PaginatedCSVRenderer (CSVRenderer):
    results_field = 'results'
    skip_pagination = True

    def render(self, data, media_type=None, renderer_context=None):
        if not isinstance(data, list):
            data = data.get(self.results_field, [])
        return super().render(data, media_type, renderer_context)

    def flatten_list(self, l):
        """ Renders the lists as a raw json-list

        Otherwise, the output number of columns is unpredictable
        """
        return {'': json.dumps(l)}
