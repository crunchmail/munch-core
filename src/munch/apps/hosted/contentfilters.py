from django.conf import settings
import lxml
import lxml.html

from .models import HostedImage
from .models import InlineImage

from munch.apps.campaigns.exceptions import WrongHTML


def handle_images(html, detach_images=False, organization=None, **kwargs):
    """ Detach base64 images and others if detach_images is enabled
    """
    tree = lxml.html.fromstring(html)

    for img in tree.cssselect('img'):
        try:
            src = img.attrib['src']
        except KeyError:
            raise WrongHTML('<img> devrait avoir un attribut "src"')
        if src.startswith('data:image/'):
            # TODO: handle ValueError
            image = InlineImage(src, organization=organization)
            url = image.store()
            img.set('src', url)
        else:
            if detach_images and organization:
                image = HostedImage(src, organization=organization)
                url = image.store()
                img.set('src', url)
    return lxml.html.tostring(tree).decode()


def set_web_link_url(text, web_view_url=None, **kwargs):
    """
    :param text_input: can be any text, including html
    """
    placeholder = settings.HOSTED['WEB_LINK_PLACEHOLDER']
    if web_view_url:
        if placeholder in text:
            return text.replace(placeholder, web_view_url)
    return text
