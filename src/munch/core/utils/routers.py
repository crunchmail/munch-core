import copy

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.routers import SimpleRouter
from rest_framework.routers import DefaultRouter


class APIRouter(DefaultRouter):
    routes = copy.deepcopy(SimpleRouter.routes)
    routes[0].mapping.update({
        'put': 'bulk_update',
        'patch': 'partial_bulk_update',
        'delete': 'bulk_destroy'})

    def get_api_root_view(self, api_urls):
        class APIRoot(APIView):
            def get(self, request, format=None):
                return Response({})
        return APIRoot.as_view()
