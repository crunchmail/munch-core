from django.conf.urls import url
from django.conf.urls import include

from ...utils.routers import APIRouter
from munch.urls import api_urlpatterns_v1

from . import views

router = APIRouter()
router.register('categories', views.CategoryViewSet, base_name='category')

api_urlpatterns_v1 += [url('', include(router.urls, namespace='core'))]
