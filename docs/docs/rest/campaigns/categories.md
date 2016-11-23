# Categories

Every messages (from campaigns) or batches (from transactional) needs to be linked to a category.

## Create a category

`POST /categories`

| Name | Type     | Description   |
|------|----------|---------------|
| name | string   | Category name |

### Success response

`HTTP 201 Created`

    {
      "url": "/categories/1/",
      "name": "test",
      "messages": [],
      "batches": [],
      "_links": {
        "opt_outs": {
          "href": "/categories/1/opt_outs/"
        },
        "stats": {
          "href": "/categories/1/stats/"
        },
        "messages_stats": {
          "href": "/categories/1/messages_stats/"
        }
      }
    }

## Retrieve a category

`GET /categories/:id`

## List your categories

Return your organization categories.

`GET /categories`

### Success response

Return a list of [categories](#create-a-category).

## Modify a category

Update a category.

`PUT /categories/:id`

## Delete a category

> You can only delete a category that doesn't have any
> [message](messages.md).

## List opt-outs (todo)
## Retrieve stats (todo)
## Retrieve messages stats (todo)
