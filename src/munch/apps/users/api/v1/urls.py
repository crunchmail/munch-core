from django.conf.urls import url
from django.conf.urls import include

from munch.core.utils.routers import APIRouter
from munch.urls import api_urlpatterns_v1

from . import views

router = APIRouter()
router.register(
    'organizations', views.OrganizationViewSet, base_name='organization')
router.register('users', views.MunchUserViewSet, base_name='munchuser')
router.register(
    'applications/api', views.APIApplicationViewSet,
    base_name='applications-api')
router.register(
    'applications/smtp', views.SmtpApplicationViewSet,
    base_name='applications-smtp')

urlpatterns = [
    url(
        '^users/(?P<user_pk>\d+)/regen_secret/$',
        views.RegenSecretView.as_view()),
    url(
        '^users/(?P<user_pk>\d+)/change_password/$',
        views.ChangePasswordView.as_view()),

    # Following urls are outside of r'^users/'
    url('^me/$', views.MeAPIView.as_view(), name='me'),
    url(r'^auth/password_reset/$', views.PasswordResetInitView.as_view(),
        name='api_password_reset_init'),
    url((
        r'^auth/password_reset/change/(?P<uidb64>[0-9A-Za-z_\-]+)'
        r'/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$'),
        views.PasswordResetSetView.as_view(),
        name='api_password_reset_set'),

] + router.urls

# We do not use prefix because it's impossible for DRF to register a ViewSet
# at index of Router. And some urls from users app are outside of r'^users/'
api_urlpatterns_v1 += [url('', include(urlpatterns, namespace='users'))]
