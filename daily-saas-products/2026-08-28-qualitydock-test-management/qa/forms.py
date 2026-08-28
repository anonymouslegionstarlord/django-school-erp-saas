from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import (
    Activity,
    Membership,
    Organization,
    Product,
    TestCase,
    TestExecution,
    TestRun,
    TestSuite,
)


class SignupForm(UserCreationForm):
    organization_name = forms.CharField(max_length=120, label="Company or team")
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        fields = ["organization_name", "username", "email"]

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if not commit:
            return user
        user.save()
        base_slug = slugify(self.cleaned_data["organization_name"]) or "quality-workspace"
        slug = base_slug
        suffix = 2
        while Organization.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        organization = Organization.objects.create(
            name=self.cleaned_data["organization_name"], slug=slug
        )
        Membership.objects.create(user=user, organization=organization, role=Membership.Role.OWNER)
        product = Product.objects.create(
            organization=organization,
            key="WEB",
            name="Web application",
            description="Starter product created during signup.",
            owner=user,
        )
        TestSuite.objects.create(
            organization=organization,
            product=product,
            name="Smoke tests",
            description="High-value checks for every deployment.",
        )
        return user


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["key", "name", "description", "owner", "status"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.instance.organization = organization
        self.fields["owner"].queryset = User.objects.filter(
            quality_membership__organization=organization,
            quality_membership__role__in=[Membership.Role.OWNER, Membership.Role.LEAD],
        ).order_by("username")

    def clean_key(self):
        key = self.cleaned_data["key"].strip().upper()
        duplicate = Product.objects.filter(organization=self.organization, key=key)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("A product with this key already exists.")
        return key


class TestSuiteForm(forms.ModelForm):
    class Meta:
        model = TestSuite
        fields = ["product", "name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, organization, product=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.instance.organization = organization
        self.fields["product"].queryset = organization.products.exclude(
            status=Product.Status.ARCHIVED
        )
        if product is not None:
            self.fields["product"].initial = product

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product")
        name = cleaned.get("name", "").strip()
        if product and name:
            duplicate = TestSuite.objects.filter(
                organization=self.organization, product=product, name__iexact=name
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error("name", "This product already has a suite with this name.")
        return cleaned


class TestCaseForm(forms.ModelForm):
    class Meta:
        model = TestCase
        fields = [
            "suite",
            "case_key",
            "title",
            "requirement_reference",
            "priority",
            "test_type",
            "status",
            "preconditions",
            "steps",
            "expected_result",
        ]
        widgets = {
            "preconditions": forms.Textarea(attrs={"rows": 3}),
            "steps": forms.Textarea(attrs={"rows": 7}),
            "expected_result": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, organization, product=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.instance.organization = organization
        suites = organization.test_suites.select_related("product")
        if product is not None:
            suites = suites.filter(product=product)
        self.fields["suite"].queryset = suites

    def clean_case_key(self):
        case_key = self.cleaned_data["case_key"].strip().upper()
        duplicate = TestCase.objects.filter(organization=self.organization, case_key=case_key)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("A test case with this key already exists.")
        return case_key


class TestRunForm(forms.ModelForm):
    include_ready_cases = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Create one execution for every ready test case in this product.",
    )

    class Meta:
        model = TestRun
        fields = [
            "product",
            "name",
            "target_version",
            "environment",
            "start_date",
            "due_date",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.organization = organization
        self.fields["product"].queryset = organization.products.exclude(
            status=Product.Status.ARCHIVED
        )


class ExecutionUpdateForm(forms.ModelForm):
    class Meta:
        model = TestExecution
        fields = ["assigned_to", "status", "actual_result", "defect_reference", "evidence_url"]
        widgets = {"actual_result": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.organization = organization
        self.fields["assigned_to"].queryset = User.objects.filter(
            quality_membership__organization=organization,
            quality_membership__role__in=[
                Membership.Role.OWNER,
                Membership.Role.LEAD,
                Membership.Role.TESTER,
            ],
        ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        actual_result = cleaned.get("actual_result", "").strip()
        defect_reference = cleaned.get("defect_reference", "").strip()
        if (
            status in [TestExecution.Status.FAILED, TestExecution.Status.BLOCKED]
            and not actual_result
        ):
            self.add_error("actual_result", "Describe the failure or blocker.")
        if status == TestExecution.Status.FAILED and not defect_reference:
            self.add_error("defect_reference", "Link or identify the defect for a failed test.")
        return cleaned


class CommentForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ["message"]
        widgets = {"message": forms.TextInput(attrs={"placeholder": "Add run context"})}
