from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import Contact, Deal, Membership, Organization


class SignupForm(UserCreationForm):
    email = forms.EmailField()
    organization_name = forms.CharField(max_length=120, label="Workspace name")

    class Meta:
        model = User
        fields = ("username", "email", "organization_name", "password1", "password2")

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            base = slugify(self.cleaned_data["organization_name"]) or "workspace"
            slug, counter = base, 2
            while Organization.objects.filter(slug=slug).exists():
                slug, counter = f"{base}-{counter}", counter + 1
            organization = Organization.objects.create(name=self.cleaned_data["organization_name"], slug=slug)
            Membership.objects.create(user=user, organization=organization, role=Membership.Role.OWNER)
        return user


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ("name", "company", "email", "phone")


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = ("contact", "title", "value", "stage", "expected_close")
        widgets = {"expected_close": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contact"].queryset = Contact.objects.filter(organization=organization)
