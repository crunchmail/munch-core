# Sending domains

Sending domains are required to sent messages and mails (from transactional app.)

In order to validate a domain, you'll need to pass tests (like `SPF`).

Domains are automatically checked and will be re-check regularly.

## Create a sending domain

`POST /domains`

| Name              | Type     | Description                         |
|-------------------|----------|-------------------------------------|
| name              | string   | Domain name                         |
| alt_organizations | array    | Array of children organization URLs |
| app_domain        | string   | Custom application domain           |

### Success response

`HTTP 201 Created`

	{
	  "url": "/domains/1/",
	  "name": "test.example.com",
	  "dkim_status": "pending",
	  "app_domain_status": "unknown",
	  "alt_organizations": [
	    "/organizations/2/"
	  ],
	  "app_domain": "",
	  "app_domain_status_date": null,
	  "dkim_status_date": null,
	  "_links": {
	    "revalidate": {
	      "href": "/domains/1/revalidate/"
	    }
	  }
	}

## List sending domains

`GET /domains`

List of [domains](#create-a-sending-domain).

## Retrieve a sending domain

`GET /domains/:id`

Retrieve a specific [domain](#create-a-sending-domain).

## Revalidate a domain

Request a [domain](#create-a-sending-domain) validation.

`POST /domains/:id/revalidate`
