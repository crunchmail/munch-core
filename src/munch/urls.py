from django.contrib import admin
from django.conf.urls import url
from django.conf.urls import include
from django.conf.urls.i18n import i18n_patterns

import rest_framework.urls
from rest_framework_jwt.views import refresh_jwt_token

import munch.apps.abuse.urls
import munch.apps.users.urls
import munch.apps.hosted.urls
import munch.apps.optouts.urls
import munch.apps.tracking.urls

from munch.core.views import api_root
from munch.apps.users.api.v1.views import ObtainJSONWebToken

api_urlpatterns_v1 = [
    url(r'^$', api_root, name='api-root'),
]

api_urlpatterns_v2 = [
    url(r'^$', api_root, name='api-root'),
]

urlpatterns = [
    url(r'^auth/', include(
        rest_framework.urls, namespace='rest_framework')),
    url(r'^api-token-auth', ObtainJSONWebToken.as_view()),
    url(r'^api-token-refresh', refresh_jwt_token),
    url(r'^abuse/', include(munch.apps.abuse.urls)),
    url(r'^t/', include(munch.apps.tracking.urls)),
    url(r'^h/', include(munch.apps.optouts.urls)),
    url(r'^account/', include(munch.apps.users.urls)),
    url(r'', include(munch.apps.hosted.urls)),
    url(r'^v1/', include(api_urlpatterns_v1, namespace='v1')),
    # url(r'^v2/', include(api_urlpatterns_v2, namespace='v2'))
]

urlpatterns += i18n_patterns(url(r'^admin/', admin.site.urls))
