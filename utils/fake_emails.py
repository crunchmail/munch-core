#!/usr/bin/env python3
import tempfile

_, out_path = tempfile.mkstemp()
out = open(out_path, 'w')

total = 50000

delivered = 70
bounced = 20
greylisted = 5
soft = 5

_bounced = int(bounced * total / 100)
_greylisted = int(greylisted * total / 100)
_soft = int(soft * total / 100)
_delivered = total - (_bounced + _greylisted + _soft)

out.write('email\n')

for i in range(_bounced):
    out.write('hard-test{}@smtpsink.net\n'.format(i))

for i in range(_greylisted):
    out.write('greylisted-test{}@smtpsink.net\n'.format(i))

for i in range(_soft):
    out.write('soft-test{}@smtpsink.net\n'.format(i))

for i in range(_delivered):
    out.write('delivered-test{}@smtpsink.net\n'.format(i))

print('Output: {}'.format(out_path))
print('Done.')
