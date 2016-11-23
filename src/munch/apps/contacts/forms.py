from django import forms

from .models import Contact
from .models import CollectedContact


class ParentSubscriptionForm(forms.ModelForm):
    class Meta:
        fields = ['address']


class ContactSubscriptionForm(ParentSubscriptionForm):
    class Meta(ParentSubscriptionForm.Meta):
        model = Contact


class CollectedContactSubscriptionForm(ParentSubscriptionForm):
    class Meta(ParentSubscriptionForm.Meta):
        model = CollectedContact
