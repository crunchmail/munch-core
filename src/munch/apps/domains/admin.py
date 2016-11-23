from django.contrib import admin

from .tasks import validate_sending_domain_field
from .models import SendingDomain


class SendingDomainAdmin(admin.ModelAdmin):
    readonly_fields = [
        'dkim_status', 'dkim_status_date', 'creation_date',
        'update_date', 'app_domain_status', 'app_domain_status_date']
    actions = ['revalidate']
    list_display = [
        'name', 'organization', 'creation_date',
        'update_date', 'dkim_status', 'dkim_status_date',
        'app_domain_status', 'app_domain_status_date']
    search_fields = ['name', 'app_domain']
    list_filter = [
        'creation_date', 'update_date', 'dkim_status', 'dkim_status_date',
        'app_domain_status', 'app_domain_status_date']
    filter_horizontal = ('alt_organizations',)

    def revalidate(self, request, queryset):
        for domain in queryset.only('id'):
            validate_sending_domain_field.apply_async([domain.id, 'dkim'])
            validate_sending_domain_field.apply_async(
                [domain.id, 'app_domain'])


class SendingDomainInline(admin.TabularInline):
    model = SendingDomain
    extra = 0
    ordering = ['creation_date']
    readonly_fields = [
        'creation_date', 'update_date', 'dkim_status', 'dkim_status_date']


admin.site.register(SendingDomain, SendingDomainAdmin)
