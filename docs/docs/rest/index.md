# Overview

## Current version

By default, all requests receive the `v1` version of the API.

## Schema

Depending of your setup, you can use `HTTP` and/or `HTTPS`.

Blank fields are included as `null` instead of being omitted.

All timestamps are returned in `ISO 8601`: `YYYY-MM-DDTHH:MM:SSZ`

## Root endpoint

You can issue a `GET` request to the root endpoint to get all
endpoint categories that the API supports.

## Authentication

Authentication is done with `JWT` or `HTTP Auth`.

**TODO**: Must add `JWT` and `HTTP Auth` documentation.

## Pagination

Must of ressources are paginated like that:

    {
      "count": 5022,
      "next": "/v1/recipients/?page=4",
      "previous": "/v1/recipients/?page=2",
      "page_count": 100,
      "results": []
    }

## Hypertext Application Language

Must of ressources have HAL links provided by `_link` field.

    {
      "_links": {
      "optout": {
        "href": "http://api.munch/v1/recipients/5612/optout/"
      },
      "status_log": {
        "href": "http://api.munch/v1/recipients/5612/status_log/"
      }
    }


All links are not covered by documentation right now.
