from django.conf.urls import url

from . import views

urlpatterns = [
    url(
        r'^open/(?P<identifier>.+)$',
        views.tracking_open, name='tracking-open'),
    url(
        r'^clicks/m/(?P<identifier>.+)/(?P<link_identifier>.+)$',
        views.tracking_redirect,
        name='tracking-redirect'),
    url(r'^clicks/w/(?P<web_key>.+)/(?P<link_identifier>.+)$',
        views.web_tracking_redirect, name='web-tracking-redirect'),
]
