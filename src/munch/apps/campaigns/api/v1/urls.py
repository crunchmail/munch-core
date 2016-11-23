from django.conf.urls import url
from django.conf.urls import include

from munch.core.utils.routers import APIRouter
from munch.urls import api_urlpatterns_v1

from . import views

router = APIRouter()
router.register('messages', views.MessageViewSet, base_name='message')
router.register('recipients', views.MailViewSet, base_name='recipient')
router.register('bounces', views.BouncesViewSet, base_name='bounce')
router.register(
    'attachments',
    views.MessageAttachmentViewset, base_name='messageattachment')

urlpatterns = [
    url('^messages/(?P<msg_pk>\d+)/preview_send/$',
        views.PreviewSendMessageView.as_view()),
    url('^recipients/(?P<mail_pk>\d+)/optout/$',
        views.MailOptOutView.as_view()),
] + router.urls

api_urlpatterns_v1 += [url('', include(urlpatterns, namespace='campaigns'))]
