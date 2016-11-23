# Users

Manage own user.

## Retrieve a user

Return currently logged user.

`GET /me`

### Success response

`HTTP 200 OK`

    {
      "identifier": "admin@example.com",
      "first_name": "Jane",
      "last_name": "Doe",
      "secret": "key-181d89e7a0d2a3e62c88c4d7e2",
      "groups": ["administrators"],
      "organization": "/organizations/1/",
      "_links": {
        "regen_secret": {"href": "/users/2/regen_secret/"},
        "change_password": {"href": "/users/2/change_password/"}
      }
    }

## Regenerate secret

Regenerate secret which is used for API authentication.

`POST /users/:id/regen_secret`

Empty body.

### Success response

`HTTP 200 OK`

`"LhrFLyXFYsRYMKKNDKzefjy2L1ChWM"`

## Change password

Change user password.

`POST /users/:id/change_password`

| Name         | Type     | Description      |
|--------------|----------|------------------|
| old_password | string   | Current password |
| new_password | string   | New passwsord    |

### Success response

`HTTP 200 OK`

Empty response.

If success, this request will automatically logout you.

### Error response

If `old_password` is not valid, API return an error.

`HTTP/1.1 400 Bad Request`

    {
      "old_password": [
        "Votre ancien mot de passe est incorrect."
      ]
    }
