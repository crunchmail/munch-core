import os

from django.core.files.storage import FileSystemStorage


class LocalFileSystemStorage(FileSystemStorage):

    def __init__(self, base_url, *args, **kwargs):
        super().__init__(base_url=base_url, *args, **kwargs)

    def get_available_name(self, name, max_length=None):
        # We assume that our name was properly set to a
        # unique (per organization) hash by the model
        return name

    def _save(self, name, content):
        # TODO: use content.kind set by upstream save() to force
        # Content-Disposition: attachment on type 'file'
        # using original file name (content.name)
        full_path = self.path(name)
        if os.path.exists(full_path):
            # If we're saving a duplicate, overwrite the file.
            # Needed because upstream _save() will request a new file name
            # if it already exists
            self.delete(name)

        return super()._save(name, content)
