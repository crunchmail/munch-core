import collections

from django.apps import apps
from django.conf import settings
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.decorators import api_view


@api_view(('GET',))
def api_root(request, format=None):
    if request.version == 'v1':
        data = {
            # Core
            'categories': reverse(
                'v1:core:category-list', request=request),
            # Campaigns
            'messages': reverse('v1:campaigns:message-list', request=request),
            'recipients': reverse(
                'v1:campaigns:recipient-list', request=request),
            'bounces': reverse('v1:campaigns:bounce-list', request=request),
            'attachments': reverse(
                'v1:campaigns:messageattachment-list', request=request),
            # Optouts
            'opt-outs': reverse('v1:optouts:opt-outs-list', request=request),
            # Domains
            'domains': reverse(
                'v1:domains:sendingdomain-list', request=request),
            # Users
            'applications/api': reverse(
                'v1:users:applications-api-list', request=request),
            'applications/smtp': reverse(
                'v1:users:applications-smtp-list', request=request),
            'me': reverse('v1:users:me', request=request),
            'organizations': reverse(
                'v1:users:organization-list', request=request),
            'users': reverse('v1:users:munchuser-list', request=request),
            # Upload store
            'images': reverse('v1:upload-store:image-create', request=request),
            # Transactional
            'transactional/mails': reverse(
                'v1:transactional:mail-list', request=request),
            'transactional/batches': reverse(
                'v1:transactional:batch-list', request=request)}
    elif request.version == 'v2':
        data = {
            # Core
            'categories': reverse(
                'v2:core:category-list', request=request),
            # Campaigns
            'messages': reverse('v2:campaigns:message-list', request=request),
            'recipients': reverse(
                'v2:campaigns:recipient-list', request=request),
            'bounces': reverse('v2:campaigns:bounce-list', request=request),
            'attachments': reverse(
                'v2:campaigns:messageattachment-list', request=request),
            # Optouts
            'opt-outs': reverse('v2:optouts:opt-outs-list', request=request),
            # Domains
            'domains': reverse(
                'v2:domains:sendingdomain-list', request=request),
            # Users
            'applications/api': reverse(
                'v2:users:applications-api-list', request=request),
            'applications/smtp': reverse(
                'v2:users:applications-smtp-list', request=request),
            'me': reverse('v2:users:me', request=request),
            'organizations': reverse(
                'v2:users:organization-list', request=request),
            'users': reverse('v2:users:munchuser-list', request=request),
            # Upload store
            'images': reverse('v2:upload-store:image-create', request=request),
            # Transactional
            'transactional/mails': reverse(
                'v1:transactional:mail-list', request=request),
            'transactional/batches': reverse(
                'v1:transactional:batch-list', request=request)}
    data.update({
        # Upload store
        'images': reverse('upload-store:image-create', request=request)})

    # Import external apps
    for name, config in apps.app_configs.items():
        if hasattr(config, 'is_munch_app') and config.is_munch_app:
            try:
                api_module = config.module.api
                try:
                    api_module = getattr(config.module.api, request.version)
                except AttributeError:
                    pass
                urls = api_module.get_api_root_urls(request)
                data.update(urls)
            except AttributeError:
                pass
            except:
                if settings.DEBUG:
                    raise

    return Response(collections.OrderedDict(
        sorted(data.items(), key=lambda t: t[0])))
