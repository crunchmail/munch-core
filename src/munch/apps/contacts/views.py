from django.http import Http404
from django.conf import settings
from django.utils import timezone
from django.shortcuts import render
from django.db.utils import IntegrityError
from django.core.exceptions import PermissionDenied
from django.core.exceptions import FieldDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from rest_framework.serializers import ValidationError
from ipware.ip import get_ip

from .models import Contact
from .models import ContactList
from .models import ContactQueue
from .models import AbstractContact
from .models import CollectedContact
from .forms import ContactSubscriptionForm
from .forms import CollectedContactSubscriptionForm
from .api.v1.serializers import PropertiesFieldHelper


def test_form(request, uuid):
    contact_list = None
    try:
        contact_list = ContactQueue.objects.get(uuid=uuid)
        contact_model = CollectedContact
        subscription_form = CollectedContactSubscriptionForm
    except ContactQueue.DoesNotExist:
        contact_list = ContactList.objects.get(uuid=uuid)
        contact_model = Contact
        subscription_form = ContactSubscriptionForm
    if not contact_list:
        raise Http404(
            'No ContactList or ContactQueue matches the given query.')

    data = {'properties': {}}
    if isinstance(contact_list, ContactQueue):
        data.update({'contact_queue': contact_list})
    else:
        data.update({'contact_list': contact_list})

    for field in request.POST:
        try:
            contact_model._meta.get_field(field)
            data[field] = request.POST.get(field)
        except FieldDoesNotExist:
            data['properties'][field] = request.POST.get(field)

    form = subscription_form(data=data)
    return render(
        request,
        'contact_queues/test_form.html',
        {'uuid': uuid, 'form': form})


@csrf_exempt
def subscription(request, uuid):
    """ Handle subscriptions from an external endpoint

    E.g. website of a organization

    That's why CSRF must be disabled on this view : there is no simple way the
    3rd-party website can produce a valid CSRF token in its form.
    """
    if request.method != 'POST':
        raise PermissionDenied('You cannot access this page directly.')

    contact_list = None
    try:
        contact_list = ContactQueue.objects.get(uuid=uuid)
        contact_model = CollectedContact
        subscription_form = CollectedContactSubscriptionForm
    except ContactQueue.DoesNotExist:
        contact_list = ContactList.objects.get(uuid=uuid)
        contact_model = Contact
        subscription_form = ContactSubscriptionForm
    if not contact_list:
        raise Http404(
            'No ContactList or ContactQueue matches the given query.')
    context = {}
    status_code = 201

    try:
        data = {'properties': {}}
        if isinstance(contact_list, ContactQueue):
            data.update({'contact_queue': contact_list})
        else:
            data.update({'contact_list': contact_list})

        for field in request.POST:
            try:
                contact_model._meta.get_field(field)
                data[field] = request.POST.get(field)
            except FieldDoesNotExist:
                data['properties'][field] = request.POST.get(field)

        form = subscription_form(data=data)
        if form.is_valid():
            contact = form.save(commit=False)
            if isinstance(contact_list, ContactQueue):
                cleaned_properties = PropertiesFieldHelper.to_internal_value(
                    data, reverse="contact_queue")
                contact.contact_queue = contact_list
            else:
                cleaned_properties = PropertiesFieldHelper.to_internal_value(
                    data, reverse="contact_list")
                contact.contact_list = contact_list
            contact.status = contact_model.PENDING
            contact.properties = cleaned_properties
            contact.subscription_ip = get_ip(request)
            contact.save()
            contact.apply_policies()
            context['contact'] = contact
        else:
            context['errors'] = form.errors
            status_code = 400
    except IntegrityError:
        context['errors'] = {
            '__all__': "Cette adresse est déjà en attente d'inscription."}
        status_code = 400
    except ValidationError as err:
        context['errors'] = err.detail
        status_code = 400

    return render(
        request, 'contacts/subscription.html', context, status=status_code)


def confirmation(request, uuid):
    expiration = timezone.now() -\
        settings.CONTACTS['EXPIRATIONS']['contact_queues:double-opt-in']
    filters = {
        'uuid': uuid,
        'update_date__gte': expiration,
        'status': AbstractContact.PENDING}
    contact = None
    try:
        contact = CollectedContact.objects.get(**filters)
    except CollectedContact.DoesNotExist:
        contact = Contact.objects.get(**filters)
    if not contact:
        raise Http404(
            'No Contact or CollectedContact matches the given query.')

    contact.status = AbstractContact.OK
    contact.save()
    return render(
        request, 'contacts/subscription.html', {'contact': contact})
