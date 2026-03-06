from django import forms
from .models import Profile
from django.contrib.auth.models import User
import re


def _clean_upi_id_value(upi_id):
    upi_id = (upi_id or "").strip()
    if not upi_id:
        return ""
    if not re.match(r"^[a-zA-Z0-9.\-_]{2,}@[a-zA-Z]{2,}$", upi_id):
        raise forms.ValidationError("Please enter a valid UPI ID, e.g. name@upi")
    return upi_id

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['image', 'bio', 'upi_id']

    def clean_upi_id(self):
        return _clean_upi_id_value(self.cleaned_data.get("upi_id"))


class UpiIdUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["upi_id"]

    def clean_upi_id(self):
        return _clean_upi_id_value(self.cleaned_data.get("upi_id"))
