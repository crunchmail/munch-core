from django.utils.translation import ugettext as _

from rest_framework.exceptions import APIException


class UserDisabledException(APIException):
    status_code = 403
    default_detail = _('User account is disabled')
