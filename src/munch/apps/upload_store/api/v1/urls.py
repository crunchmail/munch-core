from django.conf.urls import url
from django.conf.urls import include
from rest_framework.urlpatterns import format_suffix_patterns

from munch.urls import api_urlpatterns_v1

from . import views

urlpatterns = format_suffix_patterns([
    url(r'^$', views.api_root, name='api-root'),
    url(r'^images/?$', views.ImageCreate.as_view(), name='image-create'),
    url(
        r'^images/(?P<pk>[_\w-]+)/?$',
        views.ImageDetail.as_view(), name='image-detail'),
])

api_urlpatterns_v1 += [
    url(r'^upload-store/', include(urlpatterns, namespace='upload-store'))]
