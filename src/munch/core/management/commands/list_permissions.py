import yaml
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = "List current permissions."

    def add_arguments(self, parser):
        parser.add_argument(
            '--app', nargs='+', type=str, help='Filter app name.')
        parser.add_argument(
            '--group', nargs='+', type=str, help='Filter group name.')
        parser.add_argument(
            '--model', nargs='+', type=str, help='Filter model name.')

    def handle(self, *args, **options):
        result = {}

        permission_kwargs = {}
        if options.get('model', []):
            permission_kwargs[
                'content_type__model__in'] = options.get('model')
        if options.get('app', []):
            permission_kwargs[
                'content_type__app_label__in'] = options.get('app')

        group_kwargs = {}
        if options.get('group', []):
            group_kwargs['name__in'] = options.get('group')

        for group in Group.objects.filter(**group_kwargs):
            result.setdefault(group.name, {})
            for permission in group.permissions.filter(**permission_kwargs):
                content_type = permission.content_type
                result[group.name].setdefault(content_type.app_label, {})
                result[group.name][content_type.app_label].setdefault(
                    content_type.model, [])
                result[group.name][content_type.app_label][
                    content_type.model].append(permission.codename)

        print(yaml.dump(result))
