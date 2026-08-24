from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import Asset, Membership, Organization, Site, WorkLog, WorkOrder


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
            base = slugify(self.cleaned_data["business_name"]) or "facilities"
            slug, suffix = base, 2
            while Organization.objects.filter(slug=slug).exists():
                slug, suffix = f"{base}-{suffix}", suffix + 1
            organization = Organization.objects.create(
                name=self.cleaned_data["business_name"], slug=slug
            )
            Membership.objects.create(
                user=user, organization=organization, role=Membership.Role.OWNER
            )
        return user


class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = ("name", "address", "contact_name", "contact_phone")


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ("site", "tag", "name", "category", "condition", "installed_on")
        widgets = {"installed_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["site"].queryset = Site.objects.filter(organization=organization)


class WorkOrderForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = (
            "number",
            "title",
            "description",
            "site",
            "asset",
            "priority",
            "due_at",
        )
        widgets = {"due_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["site"].queryset = Site.objects.filter(organization=organization)
        self.fields["asset"].queryset = Asset.objects.filter(organization=organization)

    def clean(self):
        data = super().clean()
        site, asset = data.get("site"), data.get("asset")
        if site and asset and asset.site_id != site.id:
            self.add_error("asset", "The selected asset does not belong to this site.")
        return data


class WorkOrderUpdateForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = ("status", "assigned_to", "due_at")
        widgets = {"due_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(
            maintenance_membership__organization=organization,
            maintenance_membership__role__in=[Membership.Role.OWNER, Membership.Role.TECHNICIAN],
        )


class WorkLogForm(forms.ModelForm):
    class Meta:
        model = WorkLog
        fields = ("note", "hours", "cost")
