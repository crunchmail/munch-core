from django.conf import settings


def set_unsubscribe_url(
        text,
        unsubscribe_url=None,
        no_unsubscribe_placehoder_must_raise=False, **kwargs):
    """
    :param text_input: can be any text, including html
    """
    placeholder = settings.OPTOUTS['UNSUBSCRIBE_PLACEHOLDER']
    if unsubscribe_url:
        if placeholder in text:
            return text.replace(placeholder, unsubscribe_url)
        else:
            if no_unsubscribe_placehoder_must_raise:
                raise Exception('Cannot find unsubscribe placeholder')

    return text
