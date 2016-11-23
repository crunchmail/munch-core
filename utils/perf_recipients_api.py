#!/usr/bin/env python
import time
import requests

import grequests
from requests.auth import HTTPBasicAuth
from faker import Factory as FakerFactory

faker = FakerFactory.create()

TOTAL = 1000
PER_BULK = 250
NO_DELETE = False
API_URL = 'http://localhost:8000/v1'
API_KEY = 'key-181d89e7a0d2a3e62c88c4d7e2'
MESSAGE_ID = '1'


print('Total: {}'.format(TOTAL))
print('Bulk size: {}'.format(PER_BULK))


def get_recipients(number):
    recipients = []
    for i in range(0, number):
        recipients.append({
            "message": "{}/messages/{}/".format(API_URL, MESSAGE_ID),
            "to": faker.safe_email(),
            "properties": {
                "firstName": faker.first_name_female(),
                "lastName": faker.last_name_female()
            },
            "source_ref": "contact:{}".format(faker.uuid4()),
            "source_type": "zimbra-contact"})
    return recipients

auth = HTTPBasicAuth('api', API_KEY)

urls = []
total = 0
jsons = []
count = 0

post_urls = []

for bulk in range(int(TOTAL / PER_BULK)):
    raw_json = get_recipients(PER_BULK)

    post_urls.append(grequests.post(
        '{}/recipients/'.format(API_URL), auth=auth, json=raw_json))

post_start = time.time()
post_responses = grequests.map(post_urls)
post_end = time.time()

for resp in post_responses:
    print('#===[POST]===============================#')
    print('| Status Code: {}'.format(resp.status_code))
    print('| Time: {:.4}s'.format(resp.elapsed.total_seconds()))

total_inserted = 0
for resp in post_responses:
    total_inserted += len(resp.json()['results'])
    for item in resp.json()['results']:
        urls.append(item.get('url'))

print('| Objects inserted: {}'.format(total_inserted))

total += post_end - post_start

inserted_time = total

for page in range(int(TOTAL / PER_BULK)):
    page += 1
    get_start = time.time()
    get_resp = requests.get(
        '{}/recipients/?page_size={}&page={}'.format(
            API_URL, PER_BULK, page), auth=auth)
    get_end = time.time()

    total += get_end - get_start

    print('#===[GET]================================#')
    print('| Time: {:.4}s'.format(get_end - get_start))
    print('| Count: {}'.format(get_resp.json()['count']))
    print('| Objects retrieved: {}'.format(len(get_resp.json()['results'])))

retrieved_time = total - inserted_time

if not NO_DELETE:
    delete_start = time.time()
    delete_resp = requests.delete(
        '{}/recipients/'.format(API_URL), auth=auth, json=urls)
    delete_end = time.time()

    total += delete_end - delete_start

    deleted_time = total - inserted_time - retrieved_time

    print('#===[DELETE]=============================#')
    print('| Time: {:.4}s'.format(delete_end - delete_start))
    print('| Status Code: {}'.format(delete_resp.status_code))
    print('#========================================#')

print()
print('#===[STATS]==============================#')
print('| {} objects inserted in {:.4}s'.format(len(urls), inserted_time))
print('| {} objects retrieved in {:.4}s'.format(len(urls), retrieved_time))
if not NO_DELETE:
    print('| {} objects deleted in {:.4}s'.format(len(urls), deleted_time))
print('| Total: {:.4}s'.format(total))
print('#========================================#')
print()
