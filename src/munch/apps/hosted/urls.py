from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static

from . import views

urlpatterns = static(
    settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + [
        url(
            r'^archive/(?P<identifier>[\w\-]{20,35})/$',
            views.hosted_message, name='message_web_view')]
