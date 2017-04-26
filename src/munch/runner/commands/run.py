import os
import sys
import logging
from ssl import SSLContext
from ssl import PROTOCOL_SSLv23 # TODO: Switch to PROTOCOL_TLS with Py3.5.3+
from multiprocessing import cpu_count

import click

log = logging.getLogger('munch.apps.transactional')


@click.group()
def run():
    "Run a service."


@run.command()
def smtp():
    "Run smtp smarthost for transactional service."
    from gevent import monkey
    # Do not patch threads, it may lead to Django DatabaseWrapper being
    # shared between threads.
    # See: https://code.djangoproject.com/ticket/17998#comment:6
    monkey.patch_all(thread=False)

    import os
    import sys

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "munch.settings")

    from psycogreen.gevent import patch_psycopg
    patch_psycopg()

    sys.path.append(os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..')))

    import django
    django.setup()

    import time

    from django.conf import settings

    from gevent import sleep
    from gevent.pool import Pool
    from slimta.system import drop_privileges

    from munch.core.utils import monkey_patch_slimta_exception
    from munch.apps.transactional.queue import queue
    from munch.apps.transactional.edge import (
        TransactionalSmtpEdge, ProxyProtocolTransactionalSmtpEdge)
    from munch.apps.transactional.edge import EdgeValidators

    monkey_patch_slimta_exception()

    tls_settings = settings.TRANSACTIONAL.get('SMTP_SMARTHOST_TLS')

    if tls_settings is not None:
        if not isinstance(tls_settings, dict):
            raise Exception(
                ('Setting SMTP_SMARTHOST_TLS should be a dict with '
                 '"keyfile" and "certfile" keys'))

        for i in ('keyfile', 'certfile'):
            if i not in tls_settings:
                raise Exception(
                    '{} is required if you plan to offer STARTTLS support')
            else:
                path = tls_settings[i]
                if not os.access(path, os.R_OK):
                    raise Exception(
                        '{} is not readable or inexistant.'.format(path))
        ssl_context = SSLContext(PROTOCOL_SSLv23)
        ssl_context.load_cert_chain(
            tls_settings.get('certfile'), keyfile=tls_settings.get('keyfile'))
    else:
        ssl_context = None

    pool = Pool(settings.TRANSACTIONAL.get('EDGE_MAX_CONN', 200))

    edge_class = TransactionalSmtpEdge
    if settings.TRANSACTIONAL.get('PROXYPROTO_ENABLED', False):
        edge_class = ProxyProtocolTransactionalSmtpEdge

    edge = edge_class(
        (
            settings.TRANSACTIONAL.get('SMTP_BIND_HOST'),
            settings.TRANSACTIONAL.get('SMTP_BIND_PORT')),
        queue,
        data_timeout=settings.TRANSACTIONAL.get(
            'EDGE_TIMEOUTS', {}).get('data_timeout'),
        command_timeout=settings.TRANSACTIONAL.get(
            'EDGE_TIMEOUTS', {}).get('command_timeout'),
        pool=pool,
        hostname=settings.TRANSACTIONAL.get('EDGE_EHLO_AS', None),
        validator_class=EdgeValidators,
        context=ssl_context,
        auth=True,
    )

    log.info('Listening on {}:{}'.format(
        settings.TRANSACTIONAL.get('SMTP_BIND_HOST'),
        settings.TRANSACTIONAL.get('SMTP_BIND_PORT')))
    edge.start()

    if settings.TRANSACTIONAL.get('DROP_PRIVILEGES_USER') is not None:
        # ??? Really needed? See python-slimta/examples/slimta-mail.py...
        sleep(0.1)

        # If this command is run with root user (to be allowed to
        # open reserved ports like 25), we should then "switch" to a
        # normal user for security.
        drop_privileges(
            settings.TRANSACTIONAL.get('DROP_PRIVILEGES_USER'),
            settings.TRANSACTIONAL.get('DROP_PRIVILEGES_GROUP'))
        log.info('Dropping privileges to {}:{}'.format(
            settings.TRANSACTIONAL.get('DROP_PRIVILEGES_USER'),
            settings.TRANSACTIONAL.get('DROP_PRIVILEGES_GROUP')))

    try:
        edge.get()
    except KeyboardInterrupt:
        try:
            stop_timeout = settings.TRANSACTIONAL.get('SMTP_STOP_TIMEOUT', 5)
            edge.server.close()
            ts = time.time()
            log.info('Stop accepting connections.')
            if stop_timeout > 0:
                log.info(
                    'Waiting {} seconds before timing out '
                    'current connections...'.format(
                        stop_timeout))
                while time.time() - ts <= stop_timeout:
                    sleep(1.0)
            log.info('Edge stopped...')
            edge.server.stop(timeout=1)
        except KeyboardInterrupt:
            log.info('Forcing shutdown...')
            edge.server.stop(timeout=1)


@run.command()
@click.option('--pool', '-P', help=(
    'Pool implementation: prefork (default), '
    'eventlet, gevent, solo or threads.'), default='prefork')
@click.option('--hostname', '-n', help=(
    'Set custom hostname, e.g. \'w1.%h\'. Expands: %h'
    '(hostname), %n (name) and %d, (domain).'))
@click.option('--concurrency', '-c', default=cpu_count(), help=(
    'Number of child processes or threads to spawn. The '
    'default is the number of CPUs available on your system.'))
@click.option('--quiet', '-q', is_flag=True, default=False)
@click.option('--no-color', is_flag=True, default=False)
@click.option(
    '--autoreload', is_flag=True,
    default=False, help='Enable autoreloading.')
@click.option(
    '--worker-type', '-t', default=['all'], multiple=True,
    help=('Define which kind of task worker will consume.'),
    show_default=True)
@click.option(
    '--loglevel', '-l', help='Logging level',
    type=click.Choice(
        ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'FATAL']))
def worker(**options):
    "Run background worker instance."
    from django.conf import settings
    if hasattr(settings, 'CELERY_ALWAYS_EAGER') and \
            settings.CELERY_ALWAYS_EAGER:
        raise click.ClickException(
            'Disable CELERY_ALWAYS_EAGER in your '
            'settings file to spawn workers.')

    from munch.core.celery import app
    os.environ['WORKER_TYPE'] = ','.join(options.pop('worker_type')).lower()
    pool_cls = options.pop('pool')
    worker = app.Worker(
        pool_cls=pool_cls, queues=settings.CELERY_DEFAULT_QUEUE, **options)
    worker.start()
    try:
        sys.exit(worker.exitcode)
    except AttributeError:
        # `worker.exitcode` was added in a newer version of Celery:
        # https://github.com/celery/celery/commit/dc28e8a5
        # so this is an attempt to be forwards compatible
        pass


@run.command()
@click.option('--quiet', '-q', is_flag=True, default=False)
@click.option('--no-color', is_flag=True, default=False)
@click.option(
    '--autoreload', is_flag=True, default=False, help='Enable autoreloading.')
@click.option(
    '--loglevel', '-l', help='Logging level',
    type=click.Choice(
        ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'FATAL']))
def cron(**options):
    "Run periodic task dispatcher."
    from django.conf import settings
    if hasattr(settings, 'CELERY_ALWAYS_EAGER') and \
            settings.CELERY_ALWAYS_EAGER:
        raise click.ClickException(
            'Disable CELERY_ALWAYS_EAGER in your '
            'settings file to spawn workers.')

    from munch.core.celery import app
    app.Beat(**options).run()


@run.command()
def backmuncher():
    "Run smtp that handle feedback loops, unsuscribes and more."

    import django
    django.setup()

    from django.conf import settings
    from slimta.edge.smtp import SmtpEdge
    from slimta.system import drop_privileges
    from slimta.util.proxyproto import ProxyProtocol
    from slimta.relay.blackhole import BlackholeRelay

    from munch.core.mail.backmuncher import Queue

    edge_class = SmtpEdge
    if settings.BACKMUNCHER.get('PROXYPROTO_ENABLED', False):
        class ProxyProtocolSmtpEdge(ProxyProtocol, SmtpEdge):
            pass
        edge_class = ProxyProtocolSmtpEdge

    edge = edge_class(
        (
            settings.BACKMUNCHER.get('SMTP_BIND_HOST'),
            settings.BACKMUNCHER.get('SMTP_BIND_PORT')),
        Queue(BlackholeRelay()),
        hostname=settings.BACKMUNCHER.get('EDGE_EHLO_AS', None),
    )

    log.info('Listening on {}:{}'.format(
        settings.BACKMUNCHER.get('SMTP_BIND_HOST'),
        settings.BACKMUNCHER.get('SMTP_BIND_PORT')))
    edge.start()

    if settings.BACKMUNCHER.get('DROP_PRIVILEGES_USER') is not None:
        # If this command is run with root user (to be allowed to
        # open reserved ports like 25), we should then "switch" to a
        # normal user for security.
        drop_privileges(
            settings.BACKMUNCHER.get('DROP_PRIVILEGES_USER'),
            settings.BACKMUNCHER.get('DROP_PRIVILEGES_GROUP'))
        log.info('Dropping privileges to {}:{}'.format(
            settings.BACKMUNCHER.get('DROP_PRIVILEGES_USER'),
            settings.BACKMUNCHER.get('DROP_PRIVILEGES_GROUP')))

    try:
        edge.get()
    except KeyboardInterrupt:
        try:
            edge.server.close()
            log.info('Stop accepting connections.')
            log.info('Edge stopped...')
            edge.server.stop(timeout=1)
        except KeyboardInterrupt:
            log.info('Forcing shutdown...')
            edge.server.stop(timeout=1)
