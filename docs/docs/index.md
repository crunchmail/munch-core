# Munch

Munch is mostly a *REST API* which allow you to manage your email
campaigns and send it to *many* recipients.

It allow you to track your recipients opens and clicks and to manage
campaigns unsubscribes, bounces, opt-outs, sending domains checking and more.

This documentation aims to help you install Munch as developer or
user and allow you to consume its REST API.

## Scope

**Munch is**:

- a REST HTTP/API
- a dedicated infastructure to sent big amount of emails

**Munch is not**:

- a user application: you'll need to build your interface
- a spam relay (seriously?)


## Internals

Munch is a Django project built as a python package (pip installable).

- Python3.4
- Django
- DRF
- Celery
- PostgreSQL
- Redis
- RabbitMQ
