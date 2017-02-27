# Developer guide

This documentation explain how to install a dev or test setup of Munch.

## Requirements

* Python 3.4
* Docker & docker-compose

## Install

    git clone https://github.com/crunchmail/munch-core.git
    cd munch
    pip install -U virtualenv
    virtualenv -p python3.4 .venv
    make init_dev

It will:

* Boot every machines (PostgreSQL, RabbitMQ, Redis, Postfix, Spamd) with docker-compose
* Install every dependencies in your virtualenv.

You'll see default users in command output.

## Settings

Feel free to edit dev settings: *src/munch/settings/local.py*.

## Running tests

Tests use a specific settings file (*src/munch/settings/tests.py*). Then to run test suite:

    python manage.py test munch

To run linter (based on `setup.cfg`):

    flake8

# Run

Munch is composed of multiple components under `munch` command line.

- **web app**: `munch django runserver`
- **worker**: `munch run worker --worker-type=all
- **backmuncher** (incoming dsn): `munch run backmuncher`
- **cron** (scheduled tasks): `munch run cron`

```
    $ munch --help
    Usage: munch [OPTIONS] COMMAND [ARGS]...

      Munch is an emailing platform.

      Default settings module is `munch.settings` but it can be overridden with
      `DJANGO_CONFIG_MODULE` or with `--config` parameter.

    Options:
      --config PATH  Path to settings module.
      --version      Show the version and exit.
      --help         Show this message and exit.

    Commands:
      django   Execute Django subcommands.
      help     Show this message and exit.
      migrate  Run migrations (like `munch django migrate`).
      run      Run a service.
      shell    Run a Python interactive interpreter.
```
```
    $ munch run --help
    Usage: munch run [OPTIONS] COMMAND [ARGS]...

      Run a service.

    Options:
      --help  Show this message and exit.

    Commands:
      backmuncher  Run smtp that handle feedback loops,...
      cron         Run periodic task dispatcher.
      smtp         Run smtp smarthost for transactional service.
      worker       Run background worker instance.
```


## Snippets

### Sending e-mails


You may want to `apt install swaks`, and then:

    swaks -s localhost:1025 --to someone@localhost \
          --au admin --ap admin

The *domain postfix.example.com* is staticaly bound to *localhost:15625*,
regardless of what DNS actualy says. (which is the listening port of vagrant
postfix), for testing purposes.

For example, that will be sent from yom to the vagrant VM: ::

    swaks -s 127.0.0.1:1025 --to root@postfix.example.com \
          --au admin --ap admin \
          --header-X-HTTP-Return-Path http://127.0.0.1:8098/ping


### HTTP webhooks

You can run the included test server (along with celery and yom_smarthost, as explained before):

    python -m munch.utils.http_webhook_server

And run a test:

    swaks -s 127.0.0.1:1025 --to someone@localhost \
          --au admin --ap admin \
          --header-X-HTTP-Return-Path http://127.0.0.1:8098/ping

### Add or update permissions

Use `./manage.py permissions_migration <app_label>`.

### List permissions

Use `./manage.py list_permissions`.
