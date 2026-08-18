from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import Customer, Membership, Organization, Reply, Ticket


class SignupForm(UserCreationForm):
    email = forms.EmailField()
    organization_name = forms.CharField(max_length=120, label="Support workspace")

    class Meta:
        model = User
        fields = ("username", "email", "organization_name", "password1", "password2")

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            base = slugify(self.cleaned_data["organization_name"]) or "helpdesk"
            slug, suffix = base, 2
            while Organization.objects.filter(slug=slug).exists():
                slug, suffix = f"{base}-{suffix}", suffix + 1
            organization = Organization.objects.create(name=self.cleaned_data["organization_name"], slug=slug)
            Membership.objects.create(user=user, organization=organization, role=Membership.Role.OWNER)
        return user


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ("name", "email", "company")


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ("customer", "subject", "description", "category", "priority", "assigned_to")

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(organization=organization)
        self.fields["assigned_to"].queryset = User.objects.filter(support_membership__organization=organization)


class ReplyForm(forms.ModelForm):
    class Meta:
        model = Reply
        fields = ("body", "internal")
        widgets = {"body": forms.Textarea(attrs={"rows": 4, "placeholder": "Write a helpful response…"})}
