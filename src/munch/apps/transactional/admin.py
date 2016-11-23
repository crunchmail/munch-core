from django.urls import reverse
from django.contrib import admin

from munch.core.utils import pretty_json_as_html

from .models import Mail
from .models import MailBatch
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
    max_num = 0
    model = Mail
    fields = ['sender', 'recipient', 'author_url', 'message_field']
    readonly_fields = [
        'identifier', 'message', 'sender', 'recipient',
        'author_url', 'message_field']
    exclude = ['author']
    ordering = ['creation_date']

    def author_url(self, instance):
        return '<a target="_blank" href="{}">{}</a>'.format(
            reverse('admin:users_munchuser_change', args=[instance.author.pk]),
            instance.author)
    author_url.allow_tags = True
    author_url.short_description = 'Author'

    def message_field(self, instance):
        if instance.message:
            return 'Still have a message associated (pk:{})'.format(
                instance.message.pk)
        else:
            return 'No message associated'
    message_field.short_description = 'Message'


class MailBatchAdmin(admin.ModelAdmin):
    inlines = [MailInline]
    search_fields = ['id', 'identifier', 'name']
    list_display = [
        'identifier', 'name', 'creation_date', 'author_url', 'category_url']
    list_filter = ['creation_date']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + (
                'pretty_msg_links', 'author', '_links')
        return self.readonly_fields

    def _links(self, instance):
        content = '<ul>'
        content += '<li>Category: {}</li>'.format(self.category_url(instance))
        content += '<li>Author: {}</li>'.format(self.author_url(instance))
        content += '</ul>'
        return content
    _links.allow_tags = True
    _links.short_description = 'Links'

    def pretty_msg_links(self, instance):
        return pretty_json_as_html(instance.msg_links)
    pretty_msg_links.short_description = 'msg_links'

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


class MailAdmin(admin.ModelAdmin):
    inlines = [MailStatusInline]
    search_fields = [
        'id', 'identifier', 'headers', 'sender', 'recipient']
    list_display = [
        'identifier', 'sender', 'recipient', 'creation_date', 'curstatus',
        'track_clicks', 'track_open', 'batch_url', 'author_url']
    list_filter = ['creation_date', 'curstatus', 'track_clicks', 'track_open']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + (
                'pretty_headers', 'pretty_msg_links', 'identifier',
                'track_open', 'track_clicks', 'first_status_date', 'batch',
                'author', 'latest_status_date', 'message', 'creation_date',
                'had_delay', 'sender', 'delivery_duration', 'recipient',
                'curstatus', 'message_field', '_links')
        return self.readonly_fields

    def _links(self, instance):
        content = '<ul>'
        content += '<li>Batch: {}</li>'.format(self.batch_url(instance))
        content += '<li>Author: {}</li>'.format(self.author_url(instance))
        content += '</ul>'
        return content
    _links.allow_tags = True
    _links.short_description = 'Links'

    def author_url(self, instance):
        return '<a target="_blank" href="{}">{}</a>'.format(
            reverse('admin:users_munchuser_change', args=[instance.author.pk]),
            instance.author)
    author_url.allow_tags = True
    author_url.short_description = 'Author'

    def batch_url(self, instance):
        if instance.batch:
            return '<a target="_blank" href="{}">{}</a>'.format(
                reverse(
                    'admin:transactional_mailbatch_change',
                    args=[instance.batch.pk]),
                instance.batch)
        else:
            return 'No batch'
    batch_url.allow_tags = True
    batch_url.short_description = 'Batch'

    def message_field(self, instance):
        if instance.message:
            return 'Still have a message associated (pk:{})'.format(
                instance.message.pk)
        else:
            return 'No message associated'
    message_field.short_description = 'Message'

    def pretty_headers(self, instance):
        return pretty_json_as_html(instance.headers)
    pretty_headers.short_description = 'headers'

    def pretty_msg_links(self, instance):
        return pretty_json_as_html(instance.msg_links)
    pretty_msg_links.short_description = 'msg_links'


admin.site.register(Mail, MailAdmin)
admin.site.register(MailBatch, MailBatchAdmin)
