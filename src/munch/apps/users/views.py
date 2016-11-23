from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth import views as auth_views
from django.http.response import HttpResponseRedirect
from django.contrib.auth.password_validation import password_validators_help_text_html  # noqa

from munch.core.utils import get_login_url

from .models import MunchUser


@sensitive_post_parameters()
@never_cache
def password_reset_confirm(request, initial=False, extra_context={}, **kwargs):
    extra_context.update({
        'password_policy': password_validators_help_text_html()})

    response = auth_views.password_reset_confirm(
        request, extra_context=extra_context, **kwargs)

    if isinstance(
            response, HttpResponseRedirect) and response.status_code == 302:
        # Send password change confirmation email
        try:
            uid = force_text(urlsafe_base64_decode(kwargs['uidb64']))
            user = MunchUser.objects.get(pk=uid)
            if initial:
                user.send_invitation_complete_email()
            else:
                user.send_password_reset_complete_email()
        except (TypeError, ValueError, OverflowError, MunchUser.DoesNotExist):
            pass
    return response


def password_reset_complete(request, extra_context={}, **kwargs):
    extra_context.update({'login_url': get_login_url()})
    return auth_views.password_reset_complete(
        request, extra_context=extra_context, **kwargs)
