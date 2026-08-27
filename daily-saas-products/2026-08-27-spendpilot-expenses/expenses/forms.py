from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import (
    Activity,
    CostCenter,
    ExpenseCategory,
    ExpenseItem,
    ExpenseReport,
    Membership,
    Organization,
)


class SignupForm(UserCreationForm):
    organization_name = forms.CharField(max_length=120, label="Company name")
    base_currency = forms.ChoiceField(choices=Organization.Currency.choices)
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        fields = ["organization_name", "base_currency", "username", "email"]

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if not commit:
            return user
        user.save()
        base_slug = slugify(self.cleaned_data["organization_name"]) or "workspace"
        slug = base_slug
        counter = 2
        while Organization.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        organization = Organization.objects.create(
            name=self.cleaned_data["organization_name"],
            slug=slug,
            base_currency=self.cleaned_data["base_currency"],
        )
        Membership.objects.create(user=user, organization=organization, role=Membership.Role.OWNER)
        CostCenter.objects.create(
            organization=organization, code="GENERAL", name="General operations", manager=user
        )
        ExpenseCategory.objects.bulk_create(
            [
                ExpenseCategory(
                    organization=organization,
                    name="Travel",
                    daily_limit=10000,
                    receipt_required_over=500,
                ),
                ExpenseCategory(
                    organization=organization,
                    name="Meals",
                    daily_limit=2500,
                    receipt_required_over=500,
                ),
                ExpenseCategory(
                    organization=organization,
                    name="Software",
                    receipt_required_over=1,
                ),
            ]
        )
        return user


class ExpenseReportForm(forms.ModelForm):
    class Meta:
        model = ExpenseReport
        fields = ["title", "cost_center", "purpose", "trip_start", "trip_end"]
        widgets = {
            "purpose": forms.Textarea(attrs={"rows": 4}),
            "trip_start": forms.DateInput(attrs={"type": "date"}),
            "trip_end": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.organization = organization
        self.fields["cost_center"].queryset = organization.cost_centers.filter(active=True)


class ExpenseItemForm(forms.ModelForm):
    class Meta:
        model = ExpenseItem
        fields = [
            "category",
            "expense_date",
            "merchant",
            "description",
            "amount",
            "receipt_url",
        ]
        widgets = {"expense_date": forms.DateInput(attrs={"type": "date"})}
        help_texts = {"receipt_url": "Link to a securely stored receipt (optional)."}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.organization = organization
        self.fields["category"].queryset = organization.expense_categories.filter(active=True)


class DecisionForm(forms.Form):
    note = forms.CharField(
        max_length=1200,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Decision context or exception"}),
    )


class CommentForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ["message"]
        widgets = {"message": forms.TextInput(attrs={"placeholder": "Add an audit-trail comment"})}


class CostCenterForm(forms.ModelForm):
    class Meta:
        model = CostCenter
        fields = ["code", "name", "manager", "active"]

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.instance.organization = organization
        self.fields["manager"].queryset = User.objects.filter(
            spend_membership__organization=organization
        ).order_by("username")

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        duplicate = CostCenter.objects.filter(organization=self.organization, code=code)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("A cost center with this code already exists.")
        return code


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["name", "daily_limit", "receipt_required_over", "active"]

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.instance.organization = organization

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        duplicate = ExpenseCategory.objects.filter(
            organization=self.organization, name__iexact=name
        )
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("An expense category with this name already exists.")
        return name
