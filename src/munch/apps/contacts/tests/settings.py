from munch.settings.test import *

INSTALLED_APPS += ['munch_saas']
INSTALLED_APPS += ['munch_contacts']

############
# Contacts #
############
CONTACTS = {
    # How many contacts can we add in a single API request ?
    'MAX_BULK_CONTACTS': 10000,
    'EXPIRATIONS': {
        'contact_queues:double-opt-in': timedelta(days=7),
        'contact_queues:bounce-check': timedelta(hours=1),
        'contact_queues:consumed_lifetime': timedelta(days=7),
        'contact_queues:failed_lifetime': timedelta(days=7),
        'contact_lists:double-opt-in': timedelta(days=7),
        'contact_lists:bounce-check': timedelta(hours=1),
        'contact_lists:consumed_lifetime': timedelta(days=7),
        'contact_lists:failed_lifetime': timedelta(days=7)}
}
