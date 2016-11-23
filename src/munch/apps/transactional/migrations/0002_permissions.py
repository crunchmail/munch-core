# -*- coding: utf-8 -*-
# Generated by "permissions_migration" management command
from django.db import migrations
from django.core.management.sql import emit_post_migrate_signal

PERMISSIONS = {
    'mailbatch': [
        ('view_mailbatch', 'Can view mail batch'),
        ('view_mine_mailbatch', 'Can view_mine mail batch'),
        ('view_organizations_mailbatch', 'Can view_organizations mail batch'),
        ('add_mailbatch', 'Can add mail batch'),
        ('change_mailbatch', 'Can change mail batch'),
        ('delete_mailbatch', 'Can delete mail batch'), ],
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
    'mailstatus': [
        ('view_mailstatus', 'Can view mail status'),
        ('view_mine_mailstatus', 'Can view_mine mail status'),
        ('view_organizations_mailstatus', 'Can view_organizations mail status'),
        ('add_mailstatus', 'Can add mail status'),
        ('change_mailstatus', 'Can change mail status'),
        ('delete_mailstatus', 'Can delete mail status'), ],
}
GROUP_PERMISSIONS = {
    'administrators': {
        'mailbatch': ['view_organizations_mailbatch'],
        'mail': ['view_organizations_mail'],
        'mailstatus': ['view_organizations_mailstatus'],
    },
    'collaborators': {
        'mailbatch': ['view_organizations_mailbatch'],
        'mail': ['view_organizations_mail'],
        'mailstatus': ['view_organizations_mailstatus'],
    },
    'managers': {
        'mailbatch': ['view_organizations_mailbatch'],
        'mail': ['view_organizations_mail'],
        'mailstatus': ['view_organizations_mailstatus'],
    },
    'users': {
        'mailbatch': ['view_organizations_mailbatch'],
        'mail': ['view_organizations_mail'],
        'mailstatus': ['view_organizations_mailstatus'],
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
            app_label='transactional', model=model)
        Permission.objects.filter(content_type=content_type).delete()

    # Load permissions
    for model_name, permissions in PERMISSIONS.items():
        for permission_codename, permission_name in permissions:
            content_type = ContentType.objects.get(
                app_label='transactional', model=model_name)
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
                app_label='transactional', model=model_name)
            for codename in permissions:
                permission, _ = Permission.objects.get_or_create(
                    codename=codename, content_type_id=content_type.id)
                group.permissions.add(permission)
                group.save()


class Migration(migrations.Migration):
    dependencies = [('transactional', '0001_initial')]
    operations = [
        migrations.RunPython(update_content_types, reverse_code=None),
        migrations.RunPython(load_permissions, reverse_code=None)]