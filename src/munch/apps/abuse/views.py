from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.http import HttpResponseNotFound

from munch.core.utils import get_mail_by_identifier
from munch.apps.optouts.models import OptOut
from munch.apps.campaigns.models import PreviewMail

from .forms import AbuseNotificationForm


def abuse_report(request, identifier):
    is_test_mail = identifier.startswith('preview')
    if is_test_mail:
        mail = PreviewMail.objects.get(identifier=identifier)
    else:
        mail = get_mail_by_identifier(identifier=identifier, must_raise=False)
        if not mail:
            return HttpResponseNotFound()

    if request.method == 'POST':
        form = AbuseNotificationForm(request.POST)
        if is_test_mail:
            return HttpResponseRedirect(reverse(
                'abuse-report-thanks', kwargs={'identifier': identifier}))
        else:
            if form.is_valid():
                form.save()
                OptOut.objects.create_or_update(
                    author=mail.message.author,
                    category=mail.get_category(),
                    identifier=mail.identifier,
                    address=mail.recipient,
                    origin=OptOut.BY_ABUSE)
                return HttpResponseRedirect(reverse(
                    'abuse-report-thanks', kwargs={'identifier': identifier}))
    else:
        form = AbuseNotificationForm(initial={'mail': identifier})

    return render(
        request, 'abuse/report_abuse.html',
        {'form': form, 'mail': mail, 'is_test_mail': is_test_mail})


def abuse_report_thanks(request, identifier):
    is_test_mail = identifier.startswith('preview')
    if is_test_mail:
        mail = PreviewMail.objects.get(identifier=identifier)
    else:
        mail = get_mail_by_identifier(identifier=identifier, must_raise=False)
        if not mail:
            return HttpResponseNotFound()

    return render(
        request, 'abuse/report_thanks.html',
        {'mail': mail, 'is_test_mail': is_test_mail})
