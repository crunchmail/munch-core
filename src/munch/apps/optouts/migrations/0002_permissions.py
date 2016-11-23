# -*- coding: utf-8 -*-
from django.db import migrations
from django.core.management.sql import emit_post_migrate_signal

PERMISSIONS = {
    'optout': [
        ('add_optout', 'Can add optout'),
        ('change_mine_optout', 'Can change_mine optout'),
        ('change_optout', 'Can change optout'),
        ('change_organizations_optout', 'Can change_organizations optout'),
        ('delete_mine_optout', 'Can delete_mine optout'),
        ('delete_optout', 'Can delete optout'),
        ('delete_organizations_optout', 'Can delete_organizations optout'),
        ('view_mine_optout', 'Can view_mine optout'),
        ('view_optout', 'Can view optout'),
        ('view_organizations_optout', 'Can view_organizations optout'), ],
}
GROUP_PERMISSIONS = {
    'administrators': {
        'optout': [
            'change_organizations_optout',
            'delete_organizations_optout',
            'view_organizations_optout', ],
    },
    'managers': {
        'optout': [
            'change_organizations_optout',
            'delete_organizations_optout',
            'view_organizations_optout', ],
    },
    'users': {
        'optout': [
            'view_mine_optout', ],
    },
    'collaborators': {
        'optout': [
            'change_organizations_optout',
            'delete_organizations_optout',
            'view_organizations_optout', ],
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
            app_label='optouts', model=model)
        Permission.objects.filter(content_type=content_type).delete()

    # Load permissions
    for model_name, permissions in PERMISSIONS.items():
        for permission_codename, permission_name in permissions:
            content_type = ContentType.objects.get(
                app_label='optouts', model=model_name)
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
                app_label='optouts', model=model_name)
            for codename in permissions:
                permission, _ = Permission.objects.get_or_create(
                    codename=codename, content_type_id=content_type.id)
                group.permissions.add(permission)
                group.save()


class Migration(migrations.Migration):
    # TODO: Add your dependencies here:
    #   dependencies = [('optouts', '0001_initial')]
    dependencies = [('optouts', '0001_initial')]
    operations = [
        migrations.RunPython(update_content_types, reverse_code=None),
        migrations.RunPython(load_permissions, reverse_code=None)]
