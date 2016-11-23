from django.contrib import admin
from .models import AbuseNotification


class AbuseNotificationAdmin(admin.ModelAdmin):
    list_display = ['mail', 'contact_email', 'date']
    raw_id_fields = ['mail']
    search_fields = ['mail__recipient']


admin.site.register(AbuseNotification, AbuseNotificationAdmin)
