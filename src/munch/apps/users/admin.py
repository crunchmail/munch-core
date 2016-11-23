from django.urls import reverse
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import transaction
from django.utils.translation import ugettext_lazy as _

from munch.apps.domains.admin import SendingDomainInline

from .models import MunchUser
from .models import Organization
from .models import APIApplication
from .models import SmtpApplication
from .models import OrganizationSettings
from .forms import MunchUserCreationForm


class SmtpApplicationAdmin(admin.ModelAdmin):
    list_display = ['identifier', 'username', 'secret', 'author_url']
    actions = ['regenerate_credentials']
    readonly_fields = ['username', 'secret']
    search_fields = ['identifier', 'username', 'secret', 'author__identifier']
    raw_id_fields = ['author']

    def regenerate_credentials(self, request, queryset):
        with transaction.atomic():
            for application in queryset:
                application.regen_credentials()
                application.save()

    def author_url(self, obj):
        return '<a href="{}">{}</a>'.format(
            reverse('admin:users_munchuser_change', args=[obj.author.pk]),
            obj.author.identifier)
    author_url.allow_tags = True


class SmtpApplicationInline(admin.TabularInline):
    model = SmtpApplication
    extra = 0
    readonly_fields = ['username', 'secret']


class APIApplicationInline(admin.TabularInline):
    model = APIApplication
    extra = 0
    readonly_fields = ['secret']


class APIApplicationAdmin(admin.ModelAdmin):
    list_display = ['identifier', 'secret', 'author_url']
    actions = ['regenerate_secret']
    readonly_fields = ['secret']
    search_fields = ['identifier', 'secret', 'author__identifier']
    raw_id_fields = ['author']

    def regenerate_secret(self, request, queryset):
        with transaction.atomic():
            for application in queryset:
                application.regen_secret()
                application.save()

    def author_url(self, obj):
        return '<a href="{}">{}</a>'.format(
            reverse('admin:users_munchuser_change', args=[obj.author.pk]),
            obj.author.identifier)
    author_url.allow_tags = True


class OrganizationInline(admin.TabularInline):
    model = Organization
    extra = 0
    readonly_fields = ['creation_date', 'update_date']


class OrganizationAdmin(admin.ModelAdmin):
    model = Organization
    search_fields = ['name', 'contact_email']
    readonly_fields = ['creation_date', 'update_date']
    list_display = [
        'name', 'contact_email', 'parent', 'creation_date', 'update_date']
    list_filter = [
        'can_external_optout', 'can_attach_files',
        'creation_date', 'update_date']
    raw_id_fields = ['parent']
    inlines = [OrganizationInline, SendingDomainInline]


class OrganizationSettingsAdmin(admin.ModelAdmin):
    list_display = ['organization', 'nickname']
    search_fields = ['organization__name']


class MunchUserAdmin(UserAdmin):
    """
    Presents both human and apps, so its a bit rough for now.

    Room for improvement would be to present a distinction similar to the one
    made in API.
    """
    actions = ['reset_password']
    list_display = [
        'identifier', 'full_name', 'organization', 'last_login']
    list_filter = ['is_active', 'is_admin']
    search_fields = ['identifier', 'organization__name']
    fieldsets = None
    add_form = MunchUserCreationForm
    raw_id_fields = ['organization', 'invited_by']

    readonly_fields = ['secret', 'last_login']
    ordering = ['identifier']
    inlines = [SmtpApplicationInline, APIApplicationInline]

    def get_fieldsets(self, request, obj=None):
        return super(UserAdmin, self).get_fieldsets(request, obj)

    def reset_password(self, request, queryset):
        user_qs = MunchUser.objects.filter(
            pk__in=queryset.values_list('pk', flat=True))

        for user in user_qs:
            user.send_password_reset_email()
        self.message_user(
            request,
            _('{} password reset email(s) sent').format(
                user_qs.count()))
    reset_password.short_description = _('Reset password (via email)')


MunchUserAdmin.add_fieldsets = MunchUserAdmin.fieldsets


admin.site.register(MunchUser, MunchUserAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(APIApplication, APIApplicationAdmin)
admin.site.register(SmtpApplication, SmtpApplicationAdmin)
admin.site.register(OrganizationSettings, OrganizationSettingsAdmin)
