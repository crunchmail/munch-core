from django.contrib import admin

from .models import TrackRecord


@admin.register(TrackRecord)
class TrackRecordAdmin(admin.ModelAdmin):
    list_display = ['creation_date', 'identifier', 'kind']
