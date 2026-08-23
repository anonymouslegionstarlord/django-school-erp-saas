from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import LeaveRequest, LeaveType, Membership, Organization


class SignupForm(UserCreationForm):
    email = forms.EmailField()
    company_name = forms.CharField(max_length=120)

    class Meta:
        model = User
        fields = ("username", "email", "company_name", "password1", "password2")

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            base = slugify(self.cleaned_data["company_name"]) or "team"
            slug, suffix = base, 2
            while Organization.objects.filter(slug=slug).exists():
                slug, suffix = f"{base}-{suffix}", suffix + 1
            organization = Organization.objects.create(
                name=self.cleaned_data["company_name"], slug=slug
            )
            Membership.objects.create(
                user=user, organization=organization, role=Membership.Role.OWNER
            )
            LeaveType.objects.bulk_create(
                [
                    LeaveType(organization=organization, name="Annual leave", color="#5965d8"),
                    LeaveType(organization=organization, name="Sick leave", color="#d86767"),
                ]
            )
        return user


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ("leave_type", "starts_on", "ends_on", "reason")
        widgets = {
            "starts_on": forms.DateInput(attrs={"type": "date"}),
            "ends_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organization=None, requester=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.requester = requester
        self.fields["leave_type"].queryset = LeaveType.objects.filter(organization=organization)

    def clean(self):
        data = super().clean()
        starts_on, ends_on = data.get("starts_on"), data.get("ends_on")
        if starts_on and ends_on and ends_on < starts_on:
            self.add_error("ends_on", "End date cannot be before the start date.")
        if starts_on and ends_on and self.requester:
            collision = LeaveRequest.objects.filter(
                organization=self.organization,
                requester=self.requester,
                starts_on__lte=ends_on,
                ends_on__gte=starts_on,
            ).exclude(status__in=[LeaveRequest.Status.REJECTED, LeaveRequest.Status.CANCELLED])
            if collision.exists():
                raise forms.ValidationError(
                    "You already have a leave request overlapping these dates."
                )
        return data
