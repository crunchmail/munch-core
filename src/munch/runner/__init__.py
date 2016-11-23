import os

import click
from django.utils.module_loading import import_string

import munch


@click.group()
@click.option(
    '--config',
    default='',
    envvar='DJANGO_SETTINGS_MODULE',
    help='Path to settings module.',
    metavar='PATH')
@click.version_option(version=munch.__version__)
@click.pass_context
def cli(ctx, config):
    """Munch is an emailing platform.

    Default settings module is `munch.settings` but
    it can be overridden with `DJANGO_CONFIG_MODULE`
    or with `--config` parameter.
    """
    # Elevate --config option to DJANGO_CONFIG_MODULE env var
    if config:
        os.environ['DJANGO_SETTINGS_MODULE'] = config
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'munch.settings')


list(map(lambda cmd: cli.add_command(import_string(cmd)), (
    'munch.runner.commands.run.run',
    'munch.runner.commands.help.help',
    'munch.runner.commands.django.django',
)))


def make_django_command(name, django_command=None, help=None):
    "A wrapper to convert a Django subcommand a Click command"
    if django_command is None:
        django_command = name

    @click.command(
        name=name,
        help=help,
        add_help_option=False,
        context_settings=dict(
            ignore_unknown_options=True,
        ))
    @click.argument('management_args', nargs=-1, type=click.UNPROCESSED)
    @click.pass_context
    def inner(ctx, management_args):
        from munch.runner.commands.django import django
        ctx.params['management_args'] = (django_command,) + management_args
        ctx.forward(django)

    return inner


list(map(cli.add_command, (
    make_django_command('migrate', help=(
        'Run migrations (like `munch django migrate`).')),
    make_django_command('shell', help='Run a Python interactive interpreter.')
)))


def main():
    cli(obj={}, max_content_width=100)
