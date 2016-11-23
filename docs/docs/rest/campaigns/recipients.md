# Recipients

Each recipients must be attached to a [message](messages.md), have an address and will have a status tracking.

## Create a recipient

`POST /recipients`

| Name          | Type     | Description       |
|---------------|----------|-------------------|
| to            | string   | Email address     |
| message       | string   | Message URL       |
| source_type   | string   | Free to use field |
| source_ref    | string   | Free to use field |
| properties    | object   | Free to use field |

### Success response

`HTTP 201 Created`

    {
      "url": "/recipients/1/",
      "to": "admin@example.com",
      "date": "2016-06-13T08:43:22Z",
      "message": "/messages/1/",
      "delivery_status": "unknown",
      "source_type": "",
      "source_ref": "",
      "properties": {},
      "_links": {
        "optout": {
          "href": "/recipients/1/optout/"
        },
        "status_log": {
          "href": "/recipients/1/status_log/"
        }
      }
    }

## Retrieve a recipient

`GET /recipients/:id`

## List recipients

`GET /recipients`

### Success response

Return a list of [recipients](#create-a-recipient).

> You'll probably use `GET /messages/:id/recipients` instead
> of listing all recipients of all messages.

## Modify a recipient

`PUT /recipients/:id`

> You can only delete a recipient that doesn't have a final state.

## Delete a recipient

`DELETE /recipients/:id`

> You can only delete a recipient that doesn't have a final state.

## Retrieve recipient statuses

Return every recipient statuses.

`GET /recipients/:id/status_log`

### Success response

`HTTP 200 OK`

    [
      {
        "status": "bounced",
        "creation_date": "2016-11-16T08:56:14Z",
        "raw_msg": "200: Ok"
      },
      {
        "status": "sending",
        "creation_date": "2016-11-16T08:59:01.847058Z",
        "raw_msg": ""
      },
      {
        "status": "delayed",
        "creation_date": "2016-11-16T08:51:42.685499Z",
        "raw_msg": "451 Connection failed"
      },
      {
        "status": "sending",
        "creation_date": "2016-11-16T08:51:36.420260Z",
        "raw_msg": ""
      },
      {
        "status": "queued",
        "creation_date": "2016-11-16T08:42:08.542326Z",
        "raw_msg": "Enqueued in celery"
      },
      {
        "status": "unknown",
        "creation_date": "2016-11-16T08:42:04.772406Z",
        "raw_msg": "Mail passed to infrastructure"
      }
    ]

## Opt-out a recipient

Generate an opt-out for a recipient.

`POST /recipients/:id/optout`

Empty body.

### Success response

`HTTP 200 OK`

Empty body.
