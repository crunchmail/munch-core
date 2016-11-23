# SMTP application

Manage your SMTP applications per user to allow transactional SMTP authentication.

Applications `secret` cannot be updated.
You must regenerate secret or delete it and create a new one.

## Create an application

`POST /applications/smtp`

| Name       | Type   | Description            |
|------------|--------|------------------------|
| identifier | string | Application identifier |

### Success response

`HTTP 201 Created`

    {
      "url": "/applications/smtp/1/",
      "username": "xxaUVNMHSROVx98QlkE4KA",
      "secret": "NUZIjTMnQ4W_IgtVRZi6SA",
      "identifier": "test",
      "_links": {
        "regen_credentials": {
          "href": "/applications/smtp/2/regen_credentials/"
        }
      }
    }

## List applications

`GET /applications/smtp`

Return an list of [applications](#create-an-application).

## Update an application

You can only update `identifier` field with a `PUT` request.

## Delete an application

You can delete an application with a `DELETE` on application URL.

## Regenerate secret

You can regenerate an application secret by submitting a `POST` on `/applications/smtp/:id/regen_secret`.
