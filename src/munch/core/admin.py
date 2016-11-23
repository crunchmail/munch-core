from django.urls import reverse
from django.contrib import admin
from django.db.models import Count

from munch.core.models import Category
from munch.apps.campaigns.models import Message
from munch.apps.transactional.models import MailBatch


class MessageInline(admin.TabularInline):
    extra = 0
    max_num = 0
    model = Message
    fields = [
        'sender_email', 'sender_name', 'status', 'creation_date',
        'track_clicks', 'track_open', 'is_spam']
    readonly_fields = [
        'sender_email', 'sender_name', 'status', 'creation_date',
        'track_clicks', 'track_open', 'is_spam']


class MailBatchInline(admin.TabularInline):
    extra = 0
    max_num = 0
    model = MailBatch
    fields = ['name', 'creation_date']
    readonly_fields = ['name', 'creation_date']


class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'show_message_count', 'show_batch_count',
        'author_url', 'organization_url']
    search_fields = [
        'name', 'author__identifier', 'author__organization__name']
    readonly_fields = ['author_url']
    inlines = [MessageInline, MailBatchInline]
    raw_id_fields = ['author']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            batch_count=Count('mailbatches'),
            message_count=Count('messages'))

    def author_url(self, instance):
        return '<a target="_blank" href="{}">{}</a>'.format(
            reverse('admin:users_munchuser_change', args=[instance.author.pk]),
            instance.author)
    author_url.allow_tags = True
    author_url.short_description = 'Author'

    def organization_url(self, instance):
        return '<a target="_blank" href="{}">{}</a>'.format(
            reverse(
                'admin:users_organization_change',
                args=[instance.author.organization.pk]),
            instance.author.organization.name)
    organization_url.allow_tags = True
    organization_url.short_description = 'Organization'

    def show_message_count(self, instance):
        return instance.message_count
    show_message_count.admin_order_field = 'message_count'
    show_message_count.short_description = 'Messages Count'

    def show_batch_count(self, instance):
        return instance.batch_count
    show_batch_count.admin_order_field = 'batch_count'
    show_batch_count.short_description = 'Batches Count'


admin.site.register(Category, CategoryAdmin)
