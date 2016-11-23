from django.urls import reverse
from django.contrib import admin

from .models import Mail
from .models import Message
from .models import MessageAttachment
from .models import MailStatus


class MailStatusInline(admin.TabularInline):
    extra = 0
    max_num = 0
    can_delete = False
    model = MailStatus
    ordering = ['creation_date']
    readonly_fields = [
        'source_ip', 'destination_domain', 'status_code',
        'source_hostname', 'raw_msg', 'creation_date', 'status']


class MailInline(admin.TabularInline):
    extra = 0
    model = Mail
    readonly_fields = [
        'creation_date', 'first_status_date', 'latest_status_date',
        'delivery_duration', 'had_delay', 'identifier', 'curstatus']
    exclude = ['properties', 'source_type', 'source_ref']


class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'message', 'size', 'b64size']
    list_filter = ['message']
    search_fields = ['message']
    raw_id_fields = ['message']
    readonly_fields = ['size', 'b64size']


class MessageAttachmentInline(admin.TabularInline):
    extra = 0
    model = MessageAttachment
    readonly_fields = ['filename', 'size', 'b64size', 'path']


class MessageAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'author_url', 'status', 'creation_date',
        'send_date', 'completion_date', 'category_url']
    list_filter = ['status', 'creation_date', 'send_date']
    search_fields = ['name']
    inlines = [MessageAttachmentInline, MailInline]
    raw_id_fields = ['author']

    def author_url(self, instance):
        return '<a target="_blank" href="{}">{}</a>'.format(
            reverse('admin:users_munchuser_change', args=[instance.author.pk]),
            instance.author)
    author_url.allow_tags = True
    author_url.short_description = 'Author'

    def category_url(self, instance):
        if instance.category:
            return '<a target="_blank" href="{}">{}</a>'.format(
                reverse(
                    'admin:core_category_change', args=[instance.category.pk]),
                instance.category)
        else:
            return '-'
    category_url.allow_tags = True
    category_url.short_description = 'Category'


class MailStatusAdmin(admin.ModelAdmin):
    list_display = ['mail', 'status', 'creation_date']
    list_filter = ['status']


class MailAdmin(admin.ModelAdmin):
    list_display = [
        'recipient', 'creation_date', 'identifier',
        'last_status', 'message', 'had_delay']
    search_fields = ['recipient', 'identifier']
    inlines = [MailStatusInline]
    raw_id_fields = ['message']
    list_filter = ['had_delay']
    readonly_fields = [
        'creation_date', 'delivery_duration', 'last_status', 'had_delay',
        'first_status_date', 'latest_status_date', 'identifier']


admin.site.register(Mail, MailAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(MessageAttachment, MessageAttachmentAdmin)
admin.site.register(MailStatus, MailStatusAdmin)
