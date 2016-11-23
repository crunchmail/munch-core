# -*- coding: utf-8 -*-
from django.db import migrations
from django.core.management.sql import emit_post_migrate_signal

PERMISSIONS = {
    'contactlistpolicy': [
        ('add_contactlistpolicy', 'Can add contact list policy'),
        ('change_contactlistpolicy', 'Can change contact list policy'),
        ('delete_contactlistpolicy', 'Can delete contact list policy'), ],
    'contactqueuepolicyattribution': [
        ('add_contactqueuepolicyattribution', 'Can add contact queue policy attribution'),
        ('change_contactqueuepolicyattribution', 'Can change contact queue policy attribution'),
        ('delete_contactqueuepolicyattribution', 'Can delete contact queue policy attribution'), ],
    'contactlistpolicyattribution': [
        ('add_contactlistpolicyattribution', 'Can add contact list policy attribution'),
        ('change_contactlistpolicyattribution', 'Can change contact list policy attribution'),
        ('delete_contactlistpolicyattribution', 'Can delete contact list policy attribution'), ],
    'contact': [
        ('add_contact', 'Can add contact'),
        ('change_contact', 'Can change contact'),
        ('change_mine_contact', 'Can change mine contact'),
        ('change_organizations_contact', 'Can change organizations contact'),
        ('delete_contact', 'Can delete contact'),
        ('delete_mine_contact', 'Can delete mine contact'),
        ('delete_organizations_contact', 'Can delete organizations contact'),
        ('view_mine_contact', 'Can view mine contact'),
        ('view_organizations_contact', 'Can view organizations contact'), ],
    'collectedcontact': [
        ('add_collectedcontact', 'Can add collected address')
,        ('change_collectedcontact', 'Can change collected address'),
        ('delete_collectedcontact', 'Can delete collected address'), ],
    'contactlist': [
        ('add_contactlist', 'Can add liste de contacts'),
        ('change_contactlist', 'Can change liste de contacts'),
        ('change_mine_contactlist', 'Can change mine contactlist'),
        ('change_organizations_contactlist', 'Can change organizations contactlist'),
        ('delete_contactlist', 'Can delete liste de contacts'),
        ('delete_mine_contactlist', 'Can delete mine contactlist'),
        ('delete_organizations_contactlist', 'Can delete organizations contactlist'),
        ('view_mine_contactlist', 'Can view mine contactlist'),
        ('view_organizations_contactlist', 'Can view organizations contactlist'), ],
    'contactqueue': [
        ('add_contactqueue', 'Can add contact queue'),
        ('change_contactqueue', 'Can change contact queue'),
        ('change_organizations_contactqueue', 'Can change_organizations_contactqueue'),
        ('delete_contactqueue', 'Can delete contact queue'),
        ('delete_organizations_contactqueue', 'Can delete_organizations_contactqueue'),
        ('view_organizations_contactqueue', 'Can view_organizations_contactqueue'), ],
}
GROUP_PERMISSIONS = {
    'administrators': {
        'contactlistpolicy': [],
        'contactqueuepolicyattribution': [],
        'contactlistpolicyattribution': [],
        'contact': [
            'add_contact',
            'change_organizations_contact',
            'delete_organizations_contact',
            'view_organizations_contact', ],
        'collectedcontact': [],
        'contactlist': [
            'add_contactlist',
            'change_organizations_contactlist',
            'delete_contactlist',
            'delete_organizations_contactlist',
            'view_organizations_contactlist', ],
        'contactqueue': [
            'add_contactqueue',
            'change_organizations_contactqueue',
            'delete_organizations_contactqueue',
            'view_organizations_contactqueue', ],
    },
    'managers': {
        'contactlistpolicy': [],
        'contactqueuepolicyattribution': [],
        'contactlistpolicyattribution': [],
        'contact': [
            'add_contact',
            'change_organizations_contact',
            'delete_organizations_contact',
            'view_organizations_contact', ],
        'collectedcontact': [],
        'contactlist': [
            'add_contactlist',
            'change_organizations_contactlist',
            'delete_contactlist',
            'delete_organizations_contactlist',
            'view_organizations_contactlist', ],
        'contactqueue': [
            'add_contactqueue',
            'change_organizations_contactqueue',
            'delete_organizations_contactqueue',
            'view_organizations_contactqueue', ],
    },
    'users': {
        'contactlistpolicy': [],
        'contactqueuepolicyattribution': [],
        'contactlistpolicyattribution': [],
        'contact': [
            'add_contact',
            'change_mine_contact',
            'delete_mine_contact',
            'view_mine_contact', ],
        'collectedcontact': [],
        'contactlist': [
            'add_contactlist',
            'change_mine_contactlist',
            'delete_mine_contactlist',
            'view_mine_contactlist', ],
        'contactqueue': [],
    },
    'collaborators': {
        'contactlistpolicy': [],
        'contactqueuepolicyattribution': [],
        'contactlistpolicyattribution': [],
        'contact': [
            'add_contact',
            'change_organizations_contact',
            'delete_organizations_contact',
            'view_organizations_contact', ],
        'collectedcontact': [],
        'contactlist': [
            'add_contactlist',
            'change_organizations_contactlist',
            'delete_contactlist',
            'delete_organizations_contactlist',
            'view_organizations_contactlist', ],
        'contactqueue': [
            'add_contactqueue',
            'change_organizations_contactqueue',
            'delete_organizations_contactqueue',
            'view_organizations_contactqueue', ],
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
            app_label='contacts', model=model)
        Permission.objects.filter(content_type=content_type).delete()

    # Load permissions
    for model_name, permissions in PERMISSIONS.items():
        for permission_codename, permission_name in permissions:
            content_type = ContentType.objects.get(
                app_label='contacts', model=model_name)
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
                app_label='contacts', model=model_name)
            for codename in permissions:
                permission, _ = Permission.objects.get_or_create(
                    codename=codename, content_type_id=content_type.id)
                group.permissions.add(permission)
                group.save()


class Migration(migrations.Migration):
    dependencies = [('contacts', '0001_initial')]
    operations = [
        migrations.RunPython(update_content_types, reverse_code=None),
        migrations.RunPython(load_permissions, reverse_code=None)]
