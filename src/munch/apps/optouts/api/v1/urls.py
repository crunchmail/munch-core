from django.conf.urls import url
from django.conf.urls import include

from munch.core.utils.routers import APIRouter
from munch.urls import api_urlpatterns_v1

from . import views

router = APIRouter()
router.register('opt-outs', views.OptOutViewSet, base_name='opt-outs')

api_urlpatterns_v1 += [url('', include(router.urls, namespace='optouts'))]
