from django.contrib import admin

from .models import Image


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = (
        'pk', 'organization', 'width', 'upload_date',
        'expiration', 'img_preview')

    def img_preview(self, image):
        return '<a href="{url}" target="_blank">'\
               '<img src="{url}" alt="Preview" height="50" width="50"/>'\
               '</a>'.format(url=image.file.url)
    img_preview.short_description = 'Prévisualisation'
    img_preview.allow_tags = True
