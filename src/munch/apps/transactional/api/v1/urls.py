from django.conf.urls import url
from django.conf.urls import include

from munch.core.utils.routers import APIRouter
from munch.urls import api_urlpatterns_v1

from . import views

router = APIRouter()
router.register('mails', views.MailViewSet, base_name='mail')
router.register('batches', views.MailBatchViewSet, base_name='batch')

api_urlpatterns_v1 += [
    url('transactional/', include(router.urls, namespace='transactional'))]
