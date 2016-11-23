# Settings

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

    STATUS_WEBHOOK_MAX_ATTEMPTS=12 # None for infinite attempts
    STATUS_WEBHOOK_RETRY_INTERVAL=180


## Mailsend (Output SMTP)

This configure part will be moved in *Mailsend* documentation later.

*EHLO/HELO* host and output IP are by default using FQDN and system routing, but they can be overrided:

    MAILSEND['SMTP_WORKER_EHLO_AS'] = 'tartempion.example.com'
    MAILSEND['SMTP_WORKER_SRC_ADDR'] = '1.2.3.4'

(make sure the host actually has the IP and that hostname points to it).

To use Vagrant postfix vm you have to re-route `postfix.example.com` to it.

    MAILSEND['SMTP_WORKER_FORCE_MX'] = [
        {
            'domain': 'postfix.example.com',
            'destination': '127.0.0.1', 'port': 15625}]
