# -*- coding: utf-8 -*-
from django.db import migrations
from django.core.management.sql import emit_post_migrate_signal

PERMISSIONS = {
    'mailstatus': [
        ('add_mailstatus', 'Can add mail status'),
        ('change_mailstatus', 'Can change mail status'),
        ('change_mine_mailstatus', 'Can change_mine mail status'),
        ('change_organizations_mailstatus', 'Can change_organizations mail status'),
        ('delete_mailstatus', 'Can delete mail status'),
        ('delete_mine_mailstatus', 'Can delete_mine mail status'),
        ('delete_organizations_mailstatus', 'Can delete_organizations mail status'),
        ('view_mailstatus', 'Can view mail status'),
        ('view_mine_mailstatus', 'Can view_mine mail status'),
        ('view_organizations_mailstatus', 'Can view_organizations mail status'), ],
    'mail': [
        ('add_mail', 'Can add mail'),
        ('change_mail', 'Can change mail'),
        ('change_mine_mail', 'Can change_mine mail'),
        ('change_organizations_mail', 'Can change_organizations mail'),
        ('delete_mail', 'Can delete mail'),
        ('delete_mine_mail', 'Can delete_mine mail'),
        ('delete_organizations_mail', 'Can delete_organizations mail'),
        ('view_mail', 'Can view mail'),
        ('view_mine_mail', 'Can view_mine mail'),
        ('view_organizations_mail', 'Can view_organizations mail'), ],
    'message': [
        ('add_message', 'Can add Message'),
        ('change_message', 'Can change Message'),
        ('change_mine_message', 'Can change_mine Message'),
        ('change_organizations_message', 'Can change_organizations Message'),
        ('delete_message', 'Can delete Message'),
        ('delete_mine_message', 'Can delete_mine Message'),
        ('delete_organizations_message', 'Can delete_organizations Message'),
        ('previewsend_message', 'Can previewsend Message'),
        ('previewsend_mine_message', 'Can previewsend_mine Message'),
        ('previewsend_organizations_message', 'Can previewsend_organizations Message'),
        ('view_message', 'Can view Message'),
        ('view_mine_message', 'Can view_mine Message'),
        ('view_organizations_message', 'Can view_organizations Message'), ],
    'messageattachment': [
        ('add_messageattachment', 'Can add message attachment'),
        ('change_messageattachment', 'Can change message attachment'),
        ('change_mine_messageattachment', 'Can change_mine message attachment'),
        ('change_organizations_messageattachment', 'Can change_organizations message attachment'),
        ('delete_messageattachment', 'Can delete message attachment'),
        ('delete_mine_messageattachment', 'Can delete_mine message attachment'),
        ('delete_organizations_messageattachment', 'Can delete_organizations message attachment'),
        ('view_messageattachment', 'Can view message attachment'),
        ('view_mine_messageattachment', 'Can view_mine message attachment'),
        ('view_organizations_messageattachment', 'Can view_organizations message attachment'), ],
    'previewmail': [
        ('add_previewmail', 'Can add preview mail'),
        ('change_mine_previewmail', 'Can change_mine preview mail'),
        ('change_organizations_previewmail', 'Can change_organizations preview mail'),
        ('change_previewmail', 'Can change preview mail'),
        ('delete_mine_previewmail', 'Can delete_mine preview mail'),
        ('delete_organizations_previewmail', 'Can delete_organizations preview mail'),
        ('delete_previewmail', 'Can delete preview mail'),
        ('view_mine_previewmail', 'Can view_mine preview mail'),
        ('view_organizations_previewmail', 'Can view_organizations preview mail'),
        ('view_previewmail', 'Can view preview mail'), ],
}
GROUP_PERMISSIONS = {
    'administrators': {
        'mailstatus': [
            'view_organizations_mailstatus', ],
        'mail': [
            'add_mail',
            'change_organizations_mail',
            'delete_organizations_mail',
            'view_organizations_mail', ],
        'message': [
            'add_message',
            'change_organizations_message',
            'delete_organizations_message',
            'previewsend_organizations_message',
            'view_organizations_message', ],
        'messageattachment': [
            'add_messageattachment',
            'change_organizations_messageattachment',
            'delete_organizations_messageattachment',
            'view_organizations_messageattachment', ],
        'previewmail': [
            'change_organizations_previewmail',
            'delete_organizations_previewmail',
            'view_organizations_previewmail', ],
    },
    'managers': {
        'mailstatus': [
            'view_organizations_mailstatus', ],
        'mail': [
            'add_mail',
            'change_organizations_mail',
            'delete_organizations_mail',
            'view_organizations_mail', ],
        'message': [
            'add_message',
            'change_organizations_message',
            'delete_organizations_message',
            'previewsend_organizations_message',
            'view_organizations_message', ],
        'messageattachment': [
            'add_messageattachment',
            'change_organizations_messageattachment',
            'delete_organizations_messageattachment',
            'view_organizations_messageattachment', ],
        'previewmail': [
            'change_organizations_previewmail',
            'delete_organizations_previewmail',
            'view_organizations_previewmail', ],
    },
    'users': {
        'mailstatus': [
            'view_mine_mailstatus', ],
        'mail': [
            'add_mail',
            'change_mine_mail',
            'delete_mine_mail',
            'view_mine_mail', ],
        'message': [
            'add_message',
            'change_mine_message',
            'delete_mine_message',
            'previewsend_mine_message',
            'view_mine_message', ],
        'messageattachment': [
            'add_messageattachment',
            'change_mine_messageattachment',
            'delete_mine_messageattachment',
            'view_mine_messageattachment', ],
        'previewmail': [
            'view_mine_previewmail', ],
    },
    'collaborators': {
        'mailstatus': [
            'view_organizations_mailstatus', ],
        'mail': [
            'add_mail',
            'change_organizations_mail',
            'delete_organizations_mail',
            'view_organizations_mail', ],
        'message': [
            'add_message',
            'change_organizations_message',
            'delete_organizations_message',
            'previewsend_organizations_message',
            'view_organizations_message', ],
        'messageattachment': [
            'add_messageattachment',
            'change_organizations_messageattachment',
            'delete_organizations_messageattachment',
            'view_organizations_messageattachment', ],
        'previewmail': [
            'change_organizations_previewmail',
            'delete_organizations_previewmail',
            'view_organizations_previewmail', ],
    },
}


def update_content_types(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    emit_post_migrate_signal(False, 'default', db_alias)


def load_permissions(apps, schema_editor):
    Group = apps.get_model('auth', 'group')
    Permission = apps.get_model('auth', 'permission')
    ContentType = apps.get_model('contenttypes', 'contenttype')

    # Delete previous permissions
    for model in PERMISSIONS:
        content_type = ContentType.objects.get(
            app_label='campaigns', model=model)
        Permission.objects.filter(content_type=content_type).delete()

    # Load permissions
    for model_name, permissions in PERMISSIONS.items():
        for permission_codename, permission_name in permissions:
            content_type = ContentType.objects.get(
                app_label='campaigns', model=model_name)
            if not Permission.objects.filter(
                    codename=permission_codename,
                    content_type=content_type).exists():
                Permission.objects.create(
                    name=permission_name,
                    codename=permission_codename,
                    content_type=content_type)

    # Group permissions
    for group_name, models in GROUP_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        for model_name, permissions in models.items():
            content_type = ContentType.objects.get(
                app_label='campaigns', model=model_name)
            for codename in permissions:
                permission, _ = Permission.objects.get_or_create(
                    codename=codename, content_type_id=content_type.id)
                group.permissions.add(permission)
                group.save()


class Migration(migrations.Migration):
    # TODO: Add your dependencies here:
    #   dependencies = [('campaigns', '0001_initial')]
    dependencies = [('campaigns', '0001_initial')]
    operations = [
        migrations.RunPython(update_content_types, reverse_code=None),
        migrations.RunPython(load_permissions, reverse_code=None)]
