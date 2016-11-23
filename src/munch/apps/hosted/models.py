import re
import magic
import base64
import hashlib
import mimetypes
import urllib
import urllib.request

from django.core.files.base import ContentFile

from munch.apps.campaigns.exceptions import InvalidSubmitedData
from munch.apps.upload_store.models import Image

from .exceptions import TooBigMedia
from .exceptions import InvalidMimeType

mimetypes.init()


class HostedMaterial:
    """Represents a stored file (abstract classs) """
    MAX_SIZE = 1024 * 1024 * 4  # 4MiO

    def __init__(self, organization):
        self.organization = organization

    def store(self):
        if len(self.data) >= self.MAX_SIZE:
            raise TooBigMedia(self.identifying_name, self.MAX_SIZE)

        mime = magic.from_buffer(self.data, mime=True)
        if mime not in self.allowed_mimetypes:
            raise InvalidMimeType(mime)

        self.extension = mimetypes.guess_extension(mime)

        # weirdness from mimetypes
        if self.extension == '.jpe':
            self.extension = '.jpeg'

        checksum = hashlib.sha1(self.data).hexdigest()
        fn = '{}{}'.format(checksum, self.extension)

        img = Image(organization=self.organization)
        img.file.save(fn, ContentFile(self.data))
        return img.get_absolute_url()


class AbstractHostedImage(HostedMaterial):
    allowed_mimetypes = (
        'image/jpeg', 'image/gif', 'image/png', 'image/svg+xml')


class InlineImage(AbstractHostedImage):
    """ Stores an image from a data-uri XML value """
    r_data_uri = re.compile(
        r'data:(?P<mimetype>image/(jpeg|png|gif));base64,(?P<data>.*)')

    def __init__(self, data_uri, *args, **kwargs):
        """
        @param data_uri : the data-uri string
        example of valid data_uri is :

        data:image/gif;base64,R0lGODdhAQABAIABAOvr6////ywAAAAAAQABAAACAkQBADs=
        """
        super().__init__(*args, **kwargs)

        self.identifying_name = data_uri
        if len(data_uri) > 50:
            self.identifying_name = data_uri[:50] + '...'
        else:
            self.identifying_name = data_uri

        m = self.r_data_uri.match(data_uri)
        if m:
            self.data = base64.b64decode(m.group('data').encode())
        else:
            raise InvalidSubmitedData('not a data uri : {}'.format(data_uri))


class HostedImage(AbstractHostedImage):
    """ Download and stores an image from an url """
    def __init__(self, http_uri, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.identifying_name = http_uri
        response = urllib.request.urlopen(http_uri)
        self.data = response.read(self.MAX_SIZE)
