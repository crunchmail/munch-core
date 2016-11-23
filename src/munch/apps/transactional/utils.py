from munch.core.mail.exceptions import SoftFailure


def get_envelope(identifier):
    """ This method is only for email Backend """
    from .models import Mail
    try:
        return Mail.objects.get(identifier=identifier).as_envelope()
    except Mail.DoesNotExist as exc:
        raise SoftFailure(exc)


def get_envelope_from_identifier(identifier, only_headers=False):
    """ This method is for campaigns app """
    from .models import Mail
    return Mail.objects.get(identifier=identifier).as_envelope(
        must_raise=not only_headers)
