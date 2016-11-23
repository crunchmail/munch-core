from rest_framework.reverse import reverse


def get_api_root_urls(request):
    return {
        'contacts': reverse('v1:contacts:contact-list', request=request),
        'contacts/queues': reverse(
            'v1:contacts:contactqueue-list', request=request),
        'contacts/policies': reverse(
            'v1:contacts:contactlistpolicy-list', request=request),
        'contacts/lists': reverse(
            'v1:contacts:contactlist-list', request=request)}
