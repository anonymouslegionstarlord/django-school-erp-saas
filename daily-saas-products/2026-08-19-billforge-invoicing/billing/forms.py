from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import Client, Invoice, LineItem, Membership, Organization, Payment


class SignupForm(UserCreationForm):
    email = forms.EmailField()
    business_name = forms.CharField(max_length=120)

    class Meta:
        model = User
        fields = ("username", "email", "business_name", "password1", "password2")

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            base = slugify(self.cleaned_data["business_name"]) or "business"
            slug, suffix = base, 2
            while Organization.objects.filter(slug=slug).exists():
                slug, suffix = f"{base}-{suffix}", suffix + 1
            org = Organization.objects.create(name=self.cleaned_data["business_name"], slug=slug)
            Membership.objects.create(user=user, organization=org, role=Membership.Role.OWNER)
        return user


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ("name", "email", "company", "address")


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ("client", "number", "issue_date", "due_date", "tax_rate", "notes")
        widgets = {"issue_date": forms.DateInput(attrs={"type": "date"}), "due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.filter(organization=organization)


class LineItemForm(forms.ModelForm):
    class Meta:
        model = LineItem
        fields = ("description", "quantity", "unit_price")


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ("amount", "method", "reference", "paid_on")
        widgets = {"paid_on": forms.DateInput(attrs={"type": "date"})}
