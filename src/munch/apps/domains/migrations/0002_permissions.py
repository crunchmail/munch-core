# -*- coding: utf-8 -*-
from django.db import migrations
from django.core.management.sql import emit_post_migrate_signal

PERMISSIONS = {
    'sendingdomain': [
        ('add_sendingdomain', 'Can add sending domain'),
        ('change_mine_sendingdomain', 'Can change_mine sending domain'),
        ('change_organizations_sendingdomain', 'Can change_organizations sending domain'),
        ('change_sendingdomain', 'Can change sending domain'),
        ('delete_mine_sendingdomain', 'Can delete_mine sending domain'),
        ('delete_organizations_sendingdomain', 'Can delete_organizations sending domain'),
        ('delete_sendingdomain', 'Can delete sending domain'),
        ('view_mine_sendingdomain', 'Can view_mine sending domain'),
        ('view_organizations_sendingdomain', 'Can view_organizations sending domain'),
        ('view_sendingdomain', 'Can view sending domain'), ],
}
GROUP_PERMISSIONS = {
    'administrators': {
        'sendingdomain': [
            'add_sendingdomain',
            'view_organizations_sendingdomain',
            'change_organizations_sendingdomain',
            'delete_organizations_sendingdomain',
        ]
    },
    'managers': {
        'sendingdomain': [
            'view_organizations_sendingdomain'],
    },
    'users': {
        'sendingdomain': [
            'view_organizations_sendingdomain', ],
    },
    'collaborators': {
        'sendingdomain': [
            'view_organizations_sendingdomain', ],
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
            app_label='domains', model=model)
        Permission.objects.filter(content_type=content_type).delete()

    # Load permissions
    for model_name, permissions in PERMISSIONS.items():
        for permission_codename, permission_name in permissions:
            content_type = ContentType.objects.get(
                app_label='domains', model=model_name)
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
                app_label='domains', model=model_name)
            for codename in permissions:
                permission, _ = Permission.objects.get_or_create(
                    codename=codename, content_type_id=content_type.id)
                group.permissions.add(permission)
                group.save()


class Migration(migrations.Migration):
    # TODO: Add your dependencies here:
    #   dependencies = [('domains', '0001_initial')]
    dependencies = [('domains', '0001_initial')]
    operations = [
        migrations.RunPython(update_content_types, reverse_code=None),
        migrations.RunPython(load_permissions, reverse_code=None)]
