# Deploy

## Requirements

You have one API machine and one or several workers, they should all point on
the same postgresql db and the same rabbitmq.

*Warning*: make sure (using NTP for instance) that all your machines (worker, app, smtp) have and keep the good clock time or munch could get confused.

	$ apt-get install python3 python3-dev libpq-dev libxslt-dev libjpeg-dev

## Running

Start a SMTP smarthost edge: ::

	munch run smtp

Start wsgi app (*munch/wsgi.py*) with gunicorn.

Start mailsend worker with choosen role (view :ref:`workers` in documentation): ::

	munch run worker --worker-type [all|core|status|router|gc|mx]

Start Celery Beat: ::

	munch run cron
