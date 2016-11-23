import os
from io import BytesIO
from hashlib import sha1
from datetime import timedelta

import PIL.Image
from django.db import models
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import MaxValueValidator
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.utils.http import urlsafe_base64_encode
from django.utils.module_loading import import_string
from django.contrib.postgres.fields import HStoreField

from munch.core.mail.utils import mk_base64_uuid
from munch.core.utils.models import AbstractOwnedModel

from munch.apps.users.models import Organization


def get_storage():
    backend = import_string(settings.UPLOAD_STORE['BACKEND'])
    return backend(base_url=settings.UPLOAD_STORE['URL'])


def upload_to(instance, filename):
    prefix = settings.UPLOAD_STORE['URL_PREFIX'].strip('/')
    content_type = '{}s'.format(instance.__class__.__name__.lower())
    return os.path.join(
        prefix, content_type, str(instance.organization.id), filename)


class AbstractFile(AbstractOwnedModel):
    FILE = 'file'
    IMAGE = 'image'
    KIND_CHOICES = (
        (FILE, _('File')),
        (IMAGE, _('Image')))

    identifier = models.CharField(
        max_length=35, db_index=True, unique=True,
        default=mk_base64_uuid, verbose_name=_('identifier'))
    file = models.FileField(upload_to=upload_to)
    kind = models.CharField(
        max_length=10, choices=KIND_CHOICES, default=FILE,
        verbose_name=_('type'))
    original_name = models.CharField(
        max_length=100, null=True, blank=True, verbose_name=_('original name'))
    creation_date = models.DateTimeField(
        _('creation date'), default=timezone.now)
    update_date = models.DateTimeField(_('update date'), blank=True)
    organization = models.ForeignKey(
        Organization, related_name='%(class)ss',
        verbose_name=_('organization'))
    details = HStoreField(null=True, blank=True, verbose_name=_('details'))

    owner_path = 'organization'
    author_path = AbstractOwnedModel.IRRELEVANT

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Leaving it here for tests. Dunno why...
        storage = get_storage()
        self._meta.get_field('file').storage = storage
        self.file.storage = storage

    def make_hash(self, content):
        _hash = urlsafe_base64_encode(sha1(content.read()).digest()).decode()
        content.seek(0)
        return _hash

    def save(self, *args, **kwargs):
        self.update_date = timezone.now()

        if not self.original_name:
            self.original_name = self.file.name[:100]

        if self.kind == self.IMAGE:
            content = self.pre_save_kind_image()
        else:
            content = self.pre_save_kind_file()

        # Compute a filename bashed on SHA1 hash
        # to avoid duplicates
        _hash = self.make_hash(content)
        extension = os.path.splitext(self.file.name)[1]
        file_name = '{}{}'.format(_hash, extension)
        # Save the file kind so that storage backend can
        # access it if needed
        content.kind = self.kind
        # Save FieldFile with new name and possibly altered content
        self.file.save(name=file_name, content=content, save=False)

        super().save(*args, **kwargs)

    ########
    # File #
    ########

    def pre_save_kind_file(self):
        # Nothing to do, simply return unaltered content
        return self.file

    #########
    # Image #
    #########

    def pre_save_kind_image(self):
        return self.resize_image()

    def resize_image(self):
        # original code for this method came from
        # http://snipt.net/danfreak/generate-thumbnails-in-django-with-pil/

        # If there is no image associated with this.
        # do not create thumbnail
        if not self.file:
            return

        content = self.file
        max_width = settings.UPLOAD_STORE['IMAGE_MAX_WIDTH']
        if self.details:
            requested_width = self.details.get('width')
            try:
                requested_width = int(requested_width)
            except (TypeError, ValueError):
                requested_width = int(max_width)
        else:
            requested_width = int(max_width)

        # We won't resize past our max width
        resize_width = min(requested_width, max_width)
        # Set our max thumbnail size in a tuple (max width, max height)
        NEW_SIZE = (requested_width, 9999)

        # Open original photo which we want to thumbnail using PIL's Image
        image = PIL.Image.open(self.file.file)

        if resize_width > image.size[0]:
            # We don't want to upscale images
            pass
        else:
            # Convert to RGB if necessary
            # Thanks to Limodou on DjangoSnippets.org
            # http://www.djangosnippets.org/snippets/20/
            #
            # I commented this part since it messes up my png files
            #
            # if image.mode not in ('L', 'RGB'):
            #     image = image.convert('RGB')

            # We use our PIL Image object to create the thumbnail,
            # which already has a thumbnail() convenience method that
            # contrains proportions.
            # Additionally, we use Image.ANTIALIAS to make the image look
            # better. Without antialiasing the image pattern
            # artifacts may result.
            image.thumbnail(NEW_SIZE, PIL.Image.ANTIALIAS)

            # Save the resized image
            temp_handle = BytesIO()
            image.save(temp_handle, image.format, quality=90)
            temp_handle.seek(0)

            # Create a SimpleUploadedFile from the image
            # which can be saved into a FieldFile
            content = SimpleUploadedFile(
                self.file.name, temp_handle.read(),
                content_type=PIL.Image.MIME[image.format])

        self.details['width'] = str(image.size[0])
        self.details['height'] = str(image.size[1])

        return content


# class Image(AbstractFile):
#     def save(self, *args, **kwargs):
#         self.kind = self.IMAGE
#         super().save(*args, **kwargs)


###############
# Legacy code #
###############
class UploadDuplicateError(Exception):
    def __init__(self, message, instance, *args, **kwargs):
        super().__init__(message, *args, **kwargs)
        self.instance = instance


class Upload(models.Model):
    upload_date = models.DateTimeField(auto_now=True)
    expiration = models.DurationField()
    organization = models.ForeignKey(Organization, related_name='%(class)ss')

    class Meta:
        abstract = True

    def __str__(self):
        return self.file.name

    def get_absolute_url(self):
        return self.file.url

    @staticmethod
    def get_storage():
        backend = import_string(settings.UPLOAD_STORE['BACKEND'])
        return backend(base_url=settings.UPLOAD_STORE['URL'])

    @staticmethod
    def get_path(instance, filename):
        prefix = settings.UPLOAD_STORE['URL_PREFIX'].strip('/')
        content_type = '{}s'.format(instance.__class__.__name__.lower())
        return os.path.join(
            prefix, content_type, str(instance.organization.id), filename)

    def get_hash(self, fd):
        content = fd.read()
        # append organization ID to generate hash scoped per organization
        content += str(self.organization.id).encode()
        _hash = urlsafe_base64_encode(sha1(content).digest()).decode()
        fd.seek(0)
        return _hash


class Image(Upload):
    hash = models.CharField(max_length=64, primary_key=True)
    file = models.ImageField(upload_to=Upload.get_path)
    width = models.PositiveSmallIntegerField(
        default=600, validators=[MaxValueValidator(600)])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Leaving it here for tests. Dunno why...
        self._meta.get_field('file').storage = Upload.get_storage()

        self.file.storage = Upload.get_storage()
        self.initial_width = self.width

    def save(self, *args, **kwargs):
        if not self.expiration:
            self.expiration = timedelta(0)
        if self._state.adding or self.width != self.initial_width:
            self.resize_image()
            if self._state.adding:
                if Image.objects.filter(pk=self.hash).exists():
                    raise UploadDuplicateError(
                        'This image already exists', instance=self)
        super().save(*args, **kwargs)

    def resize_image(self, save=True):
        # original code for this method came from
        # http://snipt.net/danfreak/generate-thumbnails-in-django-with-pil/

        # If there is no image associated with this.
        # do not create thumbnail
        if not self.file:
            return
        requested_width = self.width
        # Set our max thumbnail size in a tuple (max width, max height)
        NEW_SIZE = (self.width, 9999)

        # Open original photo which we want to thumbnail using PIL's Image
        image = PIL.Image.open(self.file.file)

        if requested_width > image.size[0]:
            # We don't want to upscale images, record a lower width instead
            self.width = image.size[0]
        else:
            # Convert to RGB if necessary
            # Thanks to Limodou on DjangoSnippets.org
            # http://www.djangosnippets.org/snippets/20/
            #
            # I commented this part since it messes up my png files
            #
            # if image.mode not in ('L', 'RGB'):
            #     image = image.convert('RGB')

            # We use our PIL Image object to create the thumbnail,
            # which already has a thumbnail() convenience method that
            # contrains proportions.
            # Additionally, we use Image.ANTIALIAS to make the image look
            # better. Without antialiasing the image pattern
            # artifacts may result.
            image.thumbnail(NEW_SIZE, PIL.Image.ANTIALIAS)

        # Save the resized image (or original)
        temp_handle = BytesIO()
        image.save(temp_handle, image.format, quality=90)
        temp_handle.seek(0)

        # Save image to a SimpleUploadedFile which can be saved into
        # ImageField
        suf = SimpleUploadedFile(
            os.path.split(self.file.name)[-1], temp_handle.read(),
            content_type=PIL.Image.MIME[image.format])
        # Save SimpleUploadedFile into image field
        extension = suf.name.rsplit('.', 1)[-1]
        self.hash = self.get_hash(suf)
        self.file.save(
            name='{}.{}'.format(self.hash, extension), content=suf, save=False)
