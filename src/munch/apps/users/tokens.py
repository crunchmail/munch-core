from django.conf import settings
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class MunchUserTokenGenerator(PasswordResetTokenGenerator):
    """
    Based on PasswordResetTokenGenerator (django/contrib/auth/tokens.py)
    Just overwritten to accept arbitrary timeout duration.
    """
    key_salt = settings.SECRET_KEY

    def __init__(self, timeout=settings.PASSWORD_RESET_TIMEOUT_DAYS):
        self.timeout = timeout

    def check_token(self, user, token):
        # Parse the token
        try:
            ts_b36, hash = token.split("-")
        except ValueError:
            return False

        try:
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        # Check that the timestamp/uid has not been tampered with
        if not constant_time_compare(
                self._make_token_with_timestamp(user, ts), token):
            return False

        # Check the timestamp is within limit
        if (self._num_days(self._today()) - ts) > \
                self.timeout:
            return False

        return True


token_generator = MunchUserTokenGenerator()
