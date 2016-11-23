import time
import json

import lxml.etree
from lxml.cssselect import CSSSelector
from django.core import signing
from django.utils.encoding import force_text
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.http import urlsafe_base64_decode


class WebKey:
    """ Webkey protects access to model resources by signature

    One creates a webkey from a resource, and gets a token. It can be  embeded
    in URL.

    Then, a new WebKey can be instanciated with that token that contains
    signature, timestamp  and the pk of the object.

    get_instance() will return the instance only if the signature is ok.

    """
    @classmethod
    def from_instance(cls, identifier):
        """
        :param identifier: any object identifier
        :rtype: WebKey
        """
        payload = json.dumps({'t': time.time(), 'identifier': identifier})
        token = signing.Signer().sign(urlsafe_base64_encode(
            force_bytes(payload)))
        return cls(token)

    def __init__(self, token):
        self.token = token

    def get_identifier(self):
        """ Gets the instance, if token is valid.

        :param klass: the class (must be model.Model instance)
        May throw DoesNotExist
        :returns: instance if signature is ok, None else.
        """
        try:
            payload = signing.Signer().unsign(self.token)
        except signing.BadSignature:
            return None
        else:
            d = json.loads(force_text(urlsafe_base64_decode(payload)))
            return d.get('identifier')


def get_msg_links(html):
    from munch.apps.tracking.models import LinkMap

    links_selector = CSSSelector('a')
    links = []

    try:
        doc = lxml.etree.HTML(html).getroottree()
    except lxml.etree.XMLSyntaxError:
        return {}

    for link in links_selector(doc):
        original_url = link.get('href') or ''
        original_url = original_url.strip()

        if original_url.startswith('http'):
            if original_url not in links:
                links.append(original_url)

    # Store the links_map with IDs as keys
    links_maps = LinkMap.objects.bulk_create(
        [LinkMap(link=link) for link in links])

    return {lm.identifier: lm.link for lm in links_maps}
