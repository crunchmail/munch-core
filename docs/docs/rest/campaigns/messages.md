# Messages

Message are campaign main component.

## Create a message

`POST /messages`

| Name            | Type     | Description                                           |
|-----------------|----------|-------------------------------------------------------|
| name            | string   | Message name                                          |
| sender_email    | string   | Sender email (must be a valid [sending domain](todo)) |
| sender_name     | string   | Sender name                                           |
| subject         | string   | Message subject                                       |
| html            | string   | HTML                                                  |
| category        | string   | Message category URL                                  |
| properties      | object   | Message properties                                    |
| track_open      | boolean  | Enable opens tracking                                 |
| track_clicks    | boolean  | Enable clicks tracking                                |
| external_optout | boolean  | Enable external opt-outs                              |
| detach_images   | boolean  | Detach message images                                 |

#### Success response

`HTTP 201 Created`

    {
      "url": "/messages/1/",
      "id": 2,
      "name": "test",
      "sender_email": "admin@example.com",
      "sender_name": "Jan Doe",
      "subject": "My Subject",
      "html": "<body>Hello! <a href=\"UNSUBSCRIBE_URL\">Unsubscribe here!</a></body>",
      "status": "message_ok",
      "category": "/categories/1/",
      "recipient_count": 0,
      "properties": {},
      "creation_date": "2016-11-18T14:39:56.019101Z",
      "send_date": null,
      "completion_date": null,
      "track_open": false,
      "track_clicks": false,
      "external_optout": false,
      "detach_images": false,
      "spam_score": null,
      "spam_details": null,
      "is_spam": false,
      "msg_issue": "",
      "_links": {
        "preview_send": {
          "href": "/messages/1/preview_send/"
        },
        "preview": {
          "href": "/messages/1/preview/"
        },
        "preview.html": {
          "href": "/messages/1/preview.html"
        },
        "preview.txt": {
          "href": "/messages/1/preview.txt"
        },
        "recipients": {
          "href": "/messages/1/recipients/"
        },
        "bounces": {
          "href": "/messages/1/bounces/"
        },
        "opt_outs": {
          "href": "/messages/1/opt_outs/"
        },
        "stats": {
          "href": "/messages/1/stats/"
        },
        "attachments": {
          "href": "/messages/1/attachments/"
        },
        "archive_url": {
          "href": "/archive/twzaPZ5lTdaygV9GVZYpEg/"
        }
      }
    }

In order to view your message only you can use `archive_url` URL.

## List messages

List all messages you have access.

`GET /messages`

### Success response

A list of [messages](#create-a-message).

## Modify a message

Update a message object.

`PUT /messages/:id`

## Send a message

Every message with `message_ok` status can be updated to `sending` in order to trigger delivery.

`PUT /messages/:id`

## Delete a message

> You can only delete a message that doesn't have a final status.
>
> - **Non-final statuses**: `new`, `message_ok`, `messages_issues`
> - **Final statuses**: `sending`, `sent`.

`DELETE /messages/:id`

## Retrieve message preview

Get a summary of your message.

`GET /messages/:id/preview`

### Success response

`HTTP 200 OK`

    {
      "recipients": ["contact@example.com"],
      "excluded_recipients": ["already-spammed@example.com"],
      "spam_score": null,
      "is_spam": false,
      "html": "[truncated]",
      "plaintext": "[truncated]"
    }

| Name                | Type    | Description                                                            |
|---------------------|---------|------------------------------------------------------------------------|
| recipients          | array   | List of accepted [recipients](recipients.md)                           |
| excluded_recipients | array   | List of refused [recipients](recipients.md) (for example, opt-outs)    |
| spam_score          | integer | Spam score                                                             |
| is_spam             | boolean | Is considered as spam?                                                 |
| html                | string  | HTML rendered (same as [html preview](#retrieve-html-preview))         |
| text                | string  | Text rendered (same as [text preview](#retrieve-text-preview))         |

## Retrieve text preview

`GET /messages/:id/preview.txt`

## Retrieve HTML preview

`GET /messages/:id/preview.html`

## Retrieve recipients

`GET /messages/:id/recipients`

## Retrieve bounces

`GET /messages/:id/bounces`

## Retrieve opt-outs

`GET /messages/:id/opt_outs`

## Retrieve stats

Retrieve message stats.

`GET /messages/:id/stats`

### Success response

`HTTP 200 OK`

    {
      "optout": {
        "abuse": 0,
        "feedback-loop": 0,
        "total": 0,
        "web": 0,
        "mail": 0,
        "bounce": 0
      },
      "count": {
        "total": 0,
        "had_delay": 0,
        "done": 0,
        "in_transit": 0
      },
      "tracking": {
        "opened": 0,
        "open_median_time": null,
        "clicked_total": {},
        "viewed_in_browser": 0,
        "clicked": {
          "any": 0
        }
      },
      "last_status": {
        "sending": 0,
        "dropped": 0,
        "unknown": 0,
        "ignored": 0,
        "bounced": 0,
        "queued": 0,
        "delivered": 0
      },
      "timing": {
        "delivery_total": 0,
        "delivery_median": 0
      }
    }

## Retrieve attachments

`GET /messages/:id/attachments`
