from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import Activity, Contract, Counterparty, Membership, Obligation, Organization


class StyledFormMixin:
    def style_fields(self):
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "field")


class SignupForm(StyledFormMixin, UserCreationForm):
    organization_name = forms.CharField(max_length=120)
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("organization_name", "username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            base = slugify(self.cleaned_data["organization_name"]) or "workspace"
            slug, suffix = base, 2
            while Organization.objects.filter(slug=slug).exists():
                slug, suffix = f"{base}-{suffix}", suffix + 1
            organization = Organization.objects.create(
                name=self.cleaned_data["organization_name"], slug=slug
            )
            Membership.objects.create(
                user=user, organization=organization, role=Membership.Role.OWNER
            )
        return user


class CounterpartyForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Counterparty
        fields = ("name", "contact_name", "email", "phone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class ContractForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Contract
        fields = (
            "reference",
            "title",
            "kind",
            "counterparty",
            "owner",
            "value",
            "starts_on",
            "ends_on",
            "notice_days",
            "auto_renew",
            "status",
            "summary",
        )
        widgets = {
            "starts_on": forms.DateInput(attrs={"type": "date"}),
            "ends_on": forms.DateInput(attrs={"type": "date"}),
            "summary": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["counterparty"].queryset = organization.counterparties.all()
        self.fields["owner"].queryset = User.objects.filter(
            contract_membership__organization=organization
        ).order_by("username")
        self.style_fields()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("starts_on") and cleaned.get("ends_on"):
            if cleaned["ends_on"] < cleaned["starts_on"]:
                self.add_error("ends_on", "End date must be on or after the start date.")
        return cleaned


class ContractUpdateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Contract
        fields = ("status", "owner")

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = User.objects.filter(
            contract_membership__organization=organization
        ).order_by("username")
        self.style_fields()


class ObligationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Obligation
        fields = ("title", "due_on", "assigned_to")
        widgets = {"due_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(
            contract_membership__organization=organization
        ).order_by("username")
        self.style_fields()


class ActivityForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Activity
        fields = ("message",)
        widgets = {"message": forms.Textarea(attrs={"rows": 2, "placeholder": "Add a note…"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
