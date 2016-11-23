from django.conf import settings
from django.conf.urls import url
from django.urls import reverse_lazy

from .tokens import MunchUserTokenGenerator
from .forms import InvitationForm
from . import views

urlpatterns = [
    # Invitation
    url((
        r'^invitation/confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/'
        r'(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$'),
        views.password_reset_confirm,
        {
            'set_password_form': InvitationForm,
            'post_reset_redirect': reverse_lazy('invitation_complete'),
            'token_generator': MunchUserTokenGenerator(
                settings.INVITATION_TIMEOUT_DAYS),
            'template_name': 'users/invitation_confirm.html', 'initial': True},
        name='invitation_confirm'),
    url(
        r'^invitation/complete/$',
        views.password_reset_complete,
        {'template_name': 'users/invitation_complete.html'},
        name='invitation_complete'),
    # Password Reset
    url((
        r'^password/reset/(?P<uidb64>[0-9A-Za-z_\-]+)/'
        r'(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$'),
        views.password_reset_confirm,
        {
            'post_reset_redirect': reverse_lazy('password_reset_complete'),
            'token_generator': MunchUserTokenGenerator(),
            'template_name': 'users/password_reset_confirm.html'},
        name='password_reset_confirm'),
    url(
        r'^password/reset/complete/$',
        views.password_reset_complete,
        {'template_name': 'users/password_reset_complete.html'},
        name='password_reset_complete'),
]
