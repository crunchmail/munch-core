from django.urls import reverse
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.http import HttpResponseNotFound
from django.http import HttpResponseNotAllowed
from django.core.exceptions import ObjectDoesNotExist

from munch.core.utils import get_mail_by_identifier
from munch.apps.optouts.models import OptOut
from munch.apps.campaigns.models import PreviewMail


def unsubscribe(request, identifier):
    is_test_mail = identifier.startswith('preview')
    if is_test_mail:
        try:
            mail = PreviewMail.objects.get(identifier=identifier)
        except PreviewMail.DoesNotExist:
            return HttpResponseNotFound()
    else:
        try:
            mail = get_mail_by_identifier(identifier)
        except ObjectDoesNotExist:
            return HttpResponseNotFound()

    context = {'mail': mail, 'is_test_mail': is_test_mail}

    if identifier.startswith('c-') and mail.message.external_optout:
        if request.method == 'GET':
            return render(
                request, 'optouts/unsubscribe_external.html', context)
        else:
            return HttpResponseNotAllowed(['GET'])
    else:
        if request.method == 'POST':
            optout_kwargs = {
                'category': mail.get_category(), 'author': mail.get_author()}
            if not is_test_mail:
                OptOut.objects.create_or_update(
                    identifier=mail.identifier,
                    address=mail.recipient,
                    origin=OptOut.BY_WEB,
                    **optout_kwargs)
            return HttpResponseRedirect(
                reverse('unsubscribed', kwargs={'identifier': identifier}))
        else:
            return render(request, 'optouts/unsubscribe.html', context)


def unsubscribed(request, identifier):
    if identifier.startswith('preview'):
        mail = PreviewMail.objects.get(identifier=identifier)
    else:
        mail = get_mail_by_identifier(identifier)
    return render(request, 'optouts/unsubscribed.html', {'mail': mail})
