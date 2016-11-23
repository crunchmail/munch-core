# Attachments

You message attachments to add files to your messages.

## Add an attachment

Add an attachment to a message.

> Your organization need to be able to add attachments.
> This can be change in Django administration console.

`POST /attachments`

This request must be done in HTML form (not JSON body).

| Name       | Description            |
|------------|------------------------|
| message    | Message URL            |
| file       | File object            |

### Success response

`HTTP 201 Created`

    {
      "url": "/attachments/1/",
      "message": "/messages/1/",
      "filename": "example.png",
      "size": 20029,
      "size_in_mail": 26708,
      "_links": {
        "download": {
          "href": "/attachments/1/download/"
        },
        "content": {
          "href": "/attachments/1/content/"
        }
      }
    }

| Name         | Type    | Description            |
|--------------|---------|------------------------|
| url          | string  | Attachment URL         |
| message      | string  | Message URL            |
| filename     | string  | Uploaded filename      |
| size         | integer | Uploaded file size     |
| size_in_mail | integer | File size in mail      |

## List attachments

`GET /attachments`

Return a list of [attachments](#add-an-attachment).

## Modify and attachment

Update a message attachment.

`PUT /attachments/:id`

## Delete an attachment

`DELETE /attachments/:id`
