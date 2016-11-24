# Settings

Here you'll find important settings but not all settings.
You can take a look at [production.dist](https://github.com/crunchmail/munch-core/blob/master/src/munch/settings/production.dist).

## Global

```python
# RabbitMQ
BROKER_URL = 'amqp://guest:guest@127.0.0.1:5682/munch'
# PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'munch',
        'USER': 'munch',
        'PASSWORD': 'munch',
        'HOST': '127.0.0.1',
        'PORT': '15432',
    }
}
# Redis
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:16379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}
```

## Transactional (Edge)

### SSL

If you want to offer *STARTTLS* support, you should mention public certificate and private key files in settings: ::

    TRANSACTIONAL['SMTP_SMARTHOST_TLS'] = {
        'keyfile': '/home/munch/utils/ssl/postfix.example.com.key.pem',
        'certfile': '/home/munch/utils/ssl/postfix.example.com.cert.pem',
    }

You may want *certfile* to contain a certificate chain, see
[python ssl doc](https://docs.python.org/3.4/library/ssl.html#certificate-chains).

*Note: STARTTLS is then allowed but not forced*


### Authentication

At the moment, simple authentication against a map of users/passwords is
supported. By default, it's open without authentication.

To enable it:

    TRANSACTIONAL['SMTP_REQUIRE_CREDENTIALS'] = True
    TRANSACTIONAL['SMTP_CREDENTIALS'] = {'jane.doe': 'somesecretpassword'}

### Port Binding

You can tune where do the smtp smarthost daemon binds its socket:

    TRANSACTIONAL['SMTP_BIND_HOST'] = '0.0.0.0'
    TRANSACTIONAL['SMTP_BIND_PORT'] = 1026


### Webhook failures

In case HTTP webhook cannot be reached, you can tune how many times you want
them to be retried and the interval between two attempts.

    STATUS_WEBHOOK_MAX_ATTEMPTS=12  # None for infinite attempts
    STATUS_WEBHOOK_RETRY_INTERVAL=180


## Mailsend (Output SMTP)

This configure part will be moved in *Mailsend* documentation later.

*EHLO/HELO* host and output IP are by default using FQDN and system routing, but they can be overrided:

    MAILSEND['SMTP_WORKER_EHLO_AS'] = 'munch.example.com'
    MAILSEND['SMTP_WORKER_SRC_ADDR'] = '1.2.3.4'

(make sure the host actually has the IP and that hostname points to it).
