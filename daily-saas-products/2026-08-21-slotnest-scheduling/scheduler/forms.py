from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify
from .models import Appointment, Customer, Membership, Organization, Service


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
            base = slugify(self.cleaned_data["business_name"]) or "studio"
            slug, suffix = base, 2
            while Organization.objects.filter(slug=slug).exists():
                slug, suffix = f"{base}-{suffix}", suffix + 1
            org = Organization.objects.create(name=self.cleaned_data["business_name"], slug=slug)
            Membership.objects.create(user=user, organization=org, role=Membership.Role.OWNER)
        return user


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ("name", "duration_minutes", "price", "color")


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ("name", "email", "phone", "notes")


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ("customer", "service", "staff", "starts_at", "notes")
        widgets = {"starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["customer"].queryset = Customer.objects.filter(organization=organization)
        self.fields["service"].queryset = Service.objects.filter(
            organization=organization, active=True
        )
        self.fields["staff"].queryset = User.objects.filter(
            schedule_membership__organization=organization
        )

    def clean(self):
        data = super().clean()
        staff = data.get("staff")
        starts = data.get("starts_at")
        if (
            staff
            and starts
            and Appointment.objects.filter(
                organization=self.organization, staff=staff, starts_at=starts
            ).exists()
        ):
            raise forms.ValidationError("This team member already has a booking at that time.")
        return data
