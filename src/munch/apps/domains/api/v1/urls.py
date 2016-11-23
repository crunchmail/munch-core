from django.conf.urls import url
from django.conf.urls import include

from munch.core.utils.routers import APIRouter
from munch.urls import api_urlpatterns_v1

from . import views

router = APIRouter()
router.register(
    'domains', views.SendingDomainViewSet, base_name='sendingdomain')

urlpatterns = [
    url(
        '^domains/(?P<pk>\d+)/revalidate/$',
        views.SendingDomainRevalidateView.as_view()),
] + router.urls

api_urlpatterns_v1 += [url('', include(urlpatterns, namespace='domains'))]
