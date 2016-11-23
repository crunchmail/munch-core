from django import forms
from django.utils.translation import ugettext_lazy as _

from munch.apps.campaigns.models import Mail

from .models import AbuseNotification


class AbuseNotificationForm(forms.ModelForm):
    mail = forms.CharField(max_length=50, widget=forms.HiddenInput())
    contact_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('(Optional)')}))
    contact_email = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('(Optional)')}))
    comments = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': _('Comments, questions, reason for report'),
            'rows': 4
        }))

    class Meta:
        model = AbuseNotification
        exclude = ['date']

    def clean_mail(self):
        return Mail.objects.get(identifier=self.cleaned_data['mail'])
