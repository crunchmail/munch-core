from django.conf import settings
from django.conf.urls import url
from django.conf.urls import include

from munch.urls import urlpatterns

from . import views

urlpatterns += [
    url(r'^_/contacts/', include([
        url(r'^confirm/(?P<uuid>.+)/?$', views.confirmation,
            name='confirmation'),
        url(r'^list/(?P<uuid>.+)/?$', views.subscription, name='subscription'),
    ]))
]

if settings.DEBUG:
    urlpatterns.insert(
        0, url(r'^test-form/(?P<uuid>.+)/?$', views.test_form, name='test'))
