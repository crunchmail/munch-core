# Workers

## Core

`--worker-type` option: core

* Contacts and collected contacts opt-ins expirations (*periodic task*)
* Contacts and collected contacts bounce expirations (*periodic task*)
* Delete consumed contacts after an expiration time (*periodic task*)
* Delete expired and bounced contacts after an expiration time (*periodic task*)
* Handle contacts subcription confirmation email bounces

## Status

`--worker-type` option: status

* Handle DSN
* Handle Feedback loop
* Handle mail optout
* Record campaigns mail statuses
* Transactional DSN
* Transactional Webhook
* Transactional statuses

## Router

`--worker-type` option: router

* Route envelope (*mailsend*)

## MX

`--worker-type` option: mx

* Send email (*mailsend*)

## Garbage collector

`--worker-type` option: gc

* Ping workers (*mailsend, periodic task*)
* Check disabled workers (*mailsend, periodic task*)
* Dispatch queued (*mailsend, periodic task*)
* Purge raw mail (*mailsend, periodic task*)
