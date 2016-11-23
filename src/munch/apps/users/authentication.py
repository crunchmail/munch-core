from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.authentication import BasicAuthentication

from munch.apps.users.models import APIApplication


class SecretBasicAuthentication(BasicAuthentication):
    """ Uses HTTP basic scheme to login with API key

    API key is bound to the MunchUser model.
    """
    def authenticate_credentials(self, username, secret):
        """
        Authenticate the userid and secret against username and secret.

        Tightly bound to .backends.APIKeyMunchUserBackend
        """
        if username != "api":
            raise AuthenticationFailed('Invalid username')

        user = authenticate(secret=secret)
        if user and user.is_active:
            return (user, None)
        api_app = APIApplication.objects.filter(
            secret=secret, author__is_active=True).first()
        if api_app and api_app.author.is_active:
            return (api_app.author, None)

        raise AuthenticationFailed('Invalid API key')
