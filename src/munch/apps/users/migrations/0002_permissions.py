# -*- coding: utf-8 -*-
from django.db import migrations
from django.core.management.sql import emit_post_migrate_signal

PERMISSIONS = {
    'organization': [
        ('add_organization', 'Can add organization'),
        ('change_mine_organization', 'Can change_mine organization'),
        ('change_organization', 'Can change organization'),
        ('change_organizations_organization', 'Can change_organizations organization'),
        ('delete_mine_organization', 'Can delete_mine organization'),
        ('delete_organization', 'Can delete organization'),
        ('delete_organizations_organization', 'Can delete_organizations organization'),
        ('view_mine_organization', 'Can view_mine organization'),
        ('view_organization', 'Can view organization'),
        ('view_organizations_organization', 'Can view_organizations organization'),
        ('add_child_organization', 'Can add child organizations'),
        ('delete_child_organization', 'Can delete child organizations'),
        ('invite_user_organization', 'Can invite user in organization'), ],
    'organizationsettings': [
        ('add_organizationsettings', 'Can add organization settings'),
        ('change_mine_organizationsettings', 'Can change_mine organization settings'),
        ('change_organizationsettings', 'Can change organization settings'),
        ('change_organizations_organizationsettings', 'Can change_organizations organization settings'),
        ('delete_mine_organizationsettings', 'Can delete_mine organization settings'),
        ('delete_organizationsettings', 'Can delete organization settings'),
        ('delete_organizations_organizationsettings', 'Can delete_organizations organization settings'),
        ('view_mine_organizationsettings', 'Can view_mine organization settings'),
        ('view_organizationsettings', 'Can view organization settings'),
        ('view_organizations_organizationsettings', 'Can view_organizations organization settings'), ],
    'munchuser': [
        ('add_munchuser', 'Can add user'),
        ('change_mine_munchuser', 'Can change_mine user'),
        ('change_munchuser', 'Can change user'),
        ('change_organizations_munchuser', 'Can change_organizations user'),
        ('delete_mine_munchuser', 'Can delete_mine user'),
        ('delete_munchuser', 'Can delete user'),
        ('delete_organizations_munchuser', 'Can delete_organizations user'),
        ('view_mine_munchuser', 'Can view_mine user'),
        ('view_munchuser', 'Can view user'),
        ('view_organizations_munchuser', 'Can view_organizations user'), ],
    'apiapplication': [
        ('add_apiapplication', 'Can add apiapplication'),
        ('change_apiapplication', 'Can change apiapplication'),
        ('change_mine_apiapplication', 'Can change_mine apiapplication'),
        ('change_organizations_apiapplication', 'Can change_organizations apiapplication'),
        ('delete_apiapplication', 'Can delete apiapplication'),
        ('delete_mine_apiapplication', 'Can delete_mine apiapplication'),
        ('delete_organizations_apiapplication', 'Can delete_organizations apiapplication'),
        ('view_apiapplication', 'Can view apiapplication'),
        ('view_mine_apiapplication', 'Can view_mine apiapplication'),
        ('view_organizations_apiapplication', 'Can view_organizations apiapplication'), ],
    'smtpapplication': [
        ('add_smtpapplication', 'Can add smtpapplication'),
        ('change_mine_smtpapplication', 'Can change_mine smtpapplication'),
        ('change_organizations_smtpapplication', 'Can change_organizations smtpapplication'),
        ('change_smtpapplication', 'Can change smtpapplication'),
        ('delete_mine_smtpapplication', 'Can delete_mine smtpapplication'),
        ('delete_organizations_smtpapplication', 'Can delete_organizations smtpapplication'),
        ('delete_smtpapplication', 'Can delete smtpapplication'),
        ('view_mine_smtpapplication', 'Can view_mine smtpapplication'),
        ('view_organizations_smtpapplication', 'Can view_organizations smtpapplication'),
        ('view_smtpapplication', 'Can view smtpapplication'), ],
}
GROUP_PERMISSIONS = {
    'administrators': {
        'organization': [
            'view_organizations_organization',
            'change_mine_organization',
            'change_organization',
            'add_child_organization',
            'delete_child_organization',
            'invite_user_organization'],
        'organizationsettings': [],
        'munchuser': [
            'add_munchuser',
            'change_organizations_munchuser',
            'view_organizations_munchuser', ],
        'apiapplication': [
            'add_apiapplication',
            'change_organizations_apiapplication',
            'delete_organizations_apiapplication',
            'view_organizations_apiapplication', ],
        'smtpapplication': [
            'add_smtpapplication',
            'change_organizations_smtpapplication',
            'delete_organizations_smtpapplication',
            'view_organizations_smtpapplication', ],
    },
    'managers': {
        'organization': [
            'view_organizations_organization', ],
        'organizationsettings': [],
        'munchuser': [
            'change_mine_munchuser',
            'view_mine_munchuser', ],
        'apiapplication': [
            'add_apiapplication',
            'change_organizations_apiapplication',
            'delete_organizations_apiapplication',
            'view_organizations_apiapplication', ],
        'smtpapplication': [
            'add_smtpapplication',
            'change_organizations_smtpapplication',
            'delete_organizations_smtpapplication',
            'view_organizations_smtpapplication', ],
    },
    'users': {
        'organization': [
            'view_organizations_organization', ],
        'organizationsettings': [],
        'munchuser': [
            'change_mine_munchuser',
            'view_mine_munchuser', ],
        'apiapplication': [],
        'smtpapplication': [],
    },
    'collaborators': {
        'organization': [
            'view_organizations_organization', ],
        'organizationsettings': [],
        'munchuser': [
            'change_mine_munchuser',
            'view_mine_munchuser', ],
        'apiapplication': [],
        'smtpapplication': [],
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
            app_label='users', model=model)
        Permission.objects.filter(content_type=content_type).delete()

    # Load permissions
    for model_name, permissions in PERMISSIONS.items():
        for permission_codename, permission_name in permissions:
            content_type = ContentType.objects.get(
                app_label='users', model=model_name)
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
                app_label='users', model=model_name)
            for codename in permissions:
                permission, _ = Permission.objects.get_or_create(
                    codename=codename, content_type_id=content_type.id)
                group.permissions.add(permission)
                group.save()


class Migration(migrations.Migration):
    # TODO: Add your dependencies here:
    #   dependencies = [('users', '0001_initial')]
    dependencies = [('users', '0001_initial')]
    operations = [
        migrations.RunPython(update_content_types, reverse_code=None),
        migrations.RunPython(load_permissions, reverse_code=None)]
