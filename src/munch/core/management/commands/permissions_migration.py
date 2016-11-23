import logging

from django.apps import apps
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

log = logging.getLogger(__name__)

MIGRATION = """# -*- coding: utf-8 -*-
# Generated by "permissions_migration" management command
from django.db import migrations
from django.core.management.sql import emit_post_migrate_signal

{raw}

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
            app_label='{app_label}', model=model)
        Permission.objects.filter(content_type=content_type).delete()

    # Load permissions
    for model_name, permissions in PERMISSIONS.items():
        for permission_codename, permission_name in permissions:
            content_type = ContentType.objects.get(
                app_label='{app_label}', model=model_name)
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
                app_label='{app_label}', model=model_name)
            for codename in permissions:
                permission, _ = Permission.objects.get_or_create(
                    codename=codename, content_type_id=content_type.id)
                group.permissions.add(permission)
                group.save()


class Migration(migrations.Migration):
    # TODO: Add your dependencies here then remove "raise"add:
    #   dependencies = [('{app_label}', '0001_initial')]
    raise Exception('You forgot to edit "dependencies".')
    dependencies = [('{app_label}', '0001_initial')]
    operations = [
        migrations.RunPython(update_content_types, reverse_code=None),
        migrations.RunPython(load_permissions, reverse_code=None)]
"""


class Command(BaseCommand):
    help = "Get a permissions migration template."

    def add_arguments(self, parser):
        parser.add_argument('app_label', type=str, help='App label.')

    def handle(self, *args, **options):
        app_label = options.get('app_label')
        raw = "PERMISSIONS = {\n"
        for model in apps.get_app_config(app_label).get_models():
            model_name = model._meta.model_name
            raw += "    '{}': [".format(model_name)
            content_type = ContentType.objects.get(
                app_label=app_label, model=model_name)
            for permission in Permission.objects.filter(
                    content_type=content_type):
                if not permission.name:
                    log.info(
                        '"{}.{}.{}" (pk:{}) permission does '
                        'not have name.'.format(
                            app_label, model_name,
                            permission.codename, permission.pk))
                if not permission.codename:
                    log.warning(
                        '"{}.{}.{}" (pk:{}) permission does '
                        'not have codename.'.format(
                            app_label, model_name,
                            permission.codename, permission.pk))
                raw += "\n        ('{}', '{}'), ".format(
                    permission.codename.replace('\'', '\\\''),
                    permission.name.replace('\'', '\\\''))
            raw += "],\n"
        raw += "}\n"
        raw += "GROUP_PERMISSIONS = {\n"
        for group in Group.objects.all():
            raw += "    '{}': {{\n".format(group.name)
            for model in apps.get_app_config(app_label).get_models():
                model_name = model._meta.model_name
                raw += "        '{}': [".format(model_name)
                content_type = ContentType.objects.get(
                    app_label=app_label, model=model_name)
                for permission in group.permissions.filter(
                        content_type=content_type):
                    raw += "\n            '{}', ".format(permission.codename)
                raw += "],\n"
            raw += "    },\n"
        raw += "}\n"
        self.stdout.write(MIGRATION.format(app_label=app_label, raw=raw))
