import datetime
from calendar import timegm

from rest_framework_jwt.settings import api_settings


def jwt_payload_handler(user):
    """ Custom handler to not handle email and pk """
    payload = {
        'username': user.identifier,
        'exp': datetime.datetime.utcnow() + api_settings.JWT_EXPIRATION_DELTA}

    if api_settings.JWT_ALLOW_REFRESH:
        payload['orig_iat'] = timegm(datetime.datetime.utcnow().utctimetuple())

    return payload
