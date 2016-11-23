from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.forms import UserCreationForm

from .models import MunchUser


class MunchUserCreationForm(UserCreationForm):
    class Meta:
        model = MunchUser
        fields = ['identifier', 'first_name', 'last_name', 'organization']


class InvitationForm(SetPasswordForm):
    first_name = forms.CharField()
    last_name = forms.CharField()

    def save(self, commit=True):
        first_name = self.cleaned_data["first_name"]
        last_name = self.cleaned_data["last_name"]
        password = self.cleaned_data["new_password1"]
        self.user.set_password(password)
        if commit:
            self.user.is_active = True
            self.user.first_name = first_name
            self.user.last_name = last_name
            self.user.save()
        return self.user
