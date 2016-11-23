# API applications

Manage your API applications per user to allow API authentication.

Applications `secret` cannot be updated.
You must regenerate secret or delete it and create a new one.

## Create an application

`POST /applications/api`


| Name       | Type   | Description            |
|------------|--------|------------------------|
| identifier | string | Application identifier |


### Success response

`HTTP 201 Created`

    {
      "url": "/applications/api/1/",
      "identifier": "example-identifier",
      "secret": "wcGA2rqRQfqarme2dr0mdg",
      "_links": {
        "regen_secret": {
          "href": "/applications/api/1/regen_secret/"
        }
      }
    }

## List applications

`GET /applications/api`

Return an list of [applications](#create-an-application).

## Update an application

You can only update `identifier` field with a `PUT` request.

## Delete an application

You can delete an application with a `DELETE` on application URL.

## Regenerate secret

You can regenerate an application secret by submitting a `POST` on `/applications/api/:id/regen_secret`.
