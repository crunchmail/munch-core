from django.contrib import admin

from .models import OptOut


class OptOutAdmin(admin.ModelAdmin):
    list_display = ['address', 'creation_date', 'origin']
    search_fields = ['address', 'identifier']
    list_filter = ['origin']
    readonly_fields = ['creation_date']
    raw_id_fields = ['author', 'category']


admin.site.register(OptOut, OptOutAdmin)
