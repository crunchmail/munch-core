from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied


class SecretMunchUserBackend(ModelBackend):
    def authenticate(self, secret=None, **kwargs):
        """ Tries to authenticate against secret.

        Fails silently if there is no secret provided or
        Reject the authentication if there is an secret
        provided but its wrong.
        """
        UserModel = get_user_model()
        if secret:
            try:
                user = UserModel._default_manager.get(secret=secret)
                return user
            except UserModel.DoesNotExist:
                raise PermissionDenied('Invalid API credentials')
