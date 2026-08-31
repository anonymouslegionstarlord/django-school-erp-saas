from datetime import timedelta

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    Assessment,
    AssessmentControl,
    Finding,
    Membership,
    Organization,
    Vendor,
)


class SignupForm(UserCreationForm):
    organization_name = forms.CharField(max_length=140, label="Organization name")
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ["organization_name", "username", "email", "password1", "password2"]

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if not commit:
            return user
        user.save()
        base_slug = slugify(self.cleaned_data["organization_name"]) or "risk-workspace"
        slug = base_slug
        suffix = 2
        while Organization.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        organization = Organization.objects.create(
            name=self.cleaned_data["organization_name"], slug=slug
        )
        Membership.objects.create(
            organization=organization,
            user=user,
            role=Membership.Role.OWNER,
            team="Risk and compliance",
        )
        Vendor.objects.create(
            organization=organization,
            name="Example technology vendor",
            slug="example-technology-vendor",
            category=Vendor.Category.CLOUD,
            criticality=Vendor.Criticality.MEDIUM,
            status=Vendor.Status.ONBOARDING,
            service_description="Edit this vendor or add the third parties your team relies on.",
            business_owner=user,
            next_review=timezone.localdate() + timedelta(days=30),
        )
        return user


class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = [
            "name",
            "slug",
            "category",
            "criticality",
            "status",
            "service_description",
            "business_owner",
            "handles_personal_data",
            "has_production_access",
            "has_financial_access",
            "annual_spend",
            "contract_expiry",
            "next_review",
        ]
        widgets = {
            "service_description": forms.Textarea(attrs={"rows": 4}),
            "contract_expiry": forms.DateInput(attrs={"type": "date"}),
            "next_review": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["business_owner"].queryset = User.objects.filter(
            vendor_risk_membership__organization=organization
        ).order_by("first_name", "username")

    def clean_slug(self):
        slug = slugify(self.cleaned_data["slug"])
        duplicate = Vendor.objects.filter(organization=self.organization, slug=slug)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("A vendor already uses this workspace slug.")
        return slug


class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ["vendor", "title", "scope", "assessor", "due_date"]
        widgets = {
            "scope": forms.Textarea(attrs={"rows": 4}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organization, vendor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vendor"].queryset = Vendor.objects.filter(organization=organization)
        self.fields["assessor"].queryset = User.objects.filter(
            vendor_risk_membership__organization=organization,
            vendor_risk_membership__role__in=[
                Membership.Role.OWNER,
                Membership.Role.RISK_MANAGER,
                Membership.Role.ANALYST,
            ],
        ).order_by("first_name", "username")
        if vendor:
            self.fields["vendor"].initial = vendor


class ControlResponseForm(forms.ModelForm):
    class Meta:
        model = AssessmentControl
        fields = ["response", "evidence", "notes"]
        widgets = {
            "notes": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Context, exceptions, or next steps"}
            ),
            "evidence": forms.URLInput(attrs={"placeholder": "https://evidence.example/..."}),
        }


class FindingForm(forms.ModelForm):
    class Meta:
        model = Finding
        fields = ["title", "description", "severity", "owner", "due_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = User.objects.filter(
            vendor_risk_membership__organization=organization
        ).order_by("first_name", "username")


class FindingStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Finding.Status.choices)
    resolution_notes = forms.CharField(
        required=False,
        max_length=1800,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Required when resolving the finding"}
        ),
    )

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("status") == Finding.Status.RESOLVED
            and not cleaned.get("resolution_notes", "").strip()
        ):
            self.add_error("resolution_notes", "Explain how this finding was resolved.")
        return cleaned
