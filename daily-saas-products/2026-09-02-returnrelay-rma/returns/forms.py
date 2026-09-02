from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from .models import (
    Customer,
    Inspection,
    Membership,
    Organization,
    Product,
    RegisteredItem,
    ReturnClaim,
)
from .services import transition_choices


class DateInput(forms.DateInput):
    input_type = "date"


class SignupForm(UserCreationForm):
    workspace_name = forms.CharField(max_length=140, help_text="Your brand or service team")
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        fields = ["workspace_name", "username", "email", "password1", "password2"]

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            base_slug = slugify(self.cleaned_data["workspace_name"])[:42] or "workspace"
            slug = base_slug
            counter = 2
            while Organization.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            organization = Organization.objects.create(
                name=self.cleaned_data["workspace_name"], slug=slug
            )
            user.email = self.cleaned_data["email"]
            user.save(update_fields=["email"])
            Membership.objects.create(
                user=user,
                organization=organization,
                role=Membership.Role.OWNER,
                title="Returns operations owner",
            )
        return user


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "contact_name", "email", "phone"]

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        matches = Customer.objects.filter(organization=self.organization, name__iexact=name)
        if self.instance.pk:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise ValidationError("A customer with this name already exists in your workspace.")
        return name


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["sku", "name", "category", "retail_price", "warranty_months", "active"]

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization

    def clean_sku(self):
        sku = self.cleaned_data["sku"].strip().upper()
        matches = Product.objects.filter(organization=self.organization, sku__iexact=sku)
        if self.instance.pk:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise ValidationError("That SKU already exists in your workspace.")
        return sku


class RegisteredItemForm(forms.ModelForm):
    class Meta:
        model = RegisteredItem
        fields = ["product", "customer", "serial_number", "order_reference", "purchase_date"]
        widgets = {"purchase_date": DateInput()}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["product"].queryset = Product.objects.filter(
            organization=organization, active=True
        )
        self.fields["customer"].queryset = Customer.objects.filter(organization=organization)

    def clean_serial_number(self):
        serial_number = self.cleaned_data["serial_number"].strip().upper()
        matches = RegisteredItem.objects.filter(
            organization=self.organization, serial_number__iexact=serial_number
        )
        if self.instance.pk:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise ValidationError("That serial number is already registered in your workspace.")
        return serial_number


class ClaimForm(forms.ModelForm):
    class Meta:
        model = ReturnClaim
        fields = [
            "item",
            "issue_category",
            "description",
            "evidence_url",
            "requested_remedy",
            "priority",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = RegisteredItem.objects.filter(
            organization=organization
        ).select_related("product", "customer")


class TeamMemberForm(forms.Form):
    ROLE_CHOICES = [
        (Membership.Role.CLAIMS_MANAGER, "Claims manager"),
        (Membership.Role.TECHNICIAN, "Technician"),
        (Membership.Role.VIEWER, "Viewer"),
    ]

    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    title = forms.CharField(max_length=120)
    temporary_password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("That username is already in use.")
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("temporary_password")
        if password:
            provisional = User(
                username=cleaned.get("username", ""),
                email=cleaned.get("email", ""),
                first_name=cleaned.get("first_name", ""),
                last_name=cleaned.get("last_name", ""),
            )
            try:
                password_validation.validate_password(password, provisional)
            except ValidationError as exc:
                self.add_error("temporary_password", exc)
        return cleaned

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            password=self.cleaned_data["temporary_password"],
        )
        Membership.objects.create(
            user=user,
            organization=self.organization,
            role=self.cleaned_data["role"],
            title=self.cleaned_data["title"],
        )
        return user


class InspectionForm(forms.ModelForm):
    customer_update = forms.CharField(
        max_length=600,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="A plain-language update for the customer timeline.",
    )
    visible_to_customer = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = Inspection
        fields = ["condition", "fault_confirmed", "findings", "recommendation"]
        widgets = {"findings": forms.Textarea(attrs={"rows": 5})}


class TransitionForm(forms.Form):
    status = forms.ChoiceField(choices=[])
    update_message = forms.CharField(
        max_length=600, required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    rejection_reason = forms.CharField(
        max_length=1400, required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    resolution = forms.ChoiceField(
        choices=[("", "Choose a resolution")] + list(ReturnClaim.Resolution.choices),
        required=False,
    )
    resolution_summary = forms.CharField(
        max_length=1800, required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    resolution_amount = forms.DecimalField(
        max_digits=11, decimal_places=2, required=False, min_value=0
    )
    replacement_reference = forms.CharField(max_length=100, required=False)
    visible_to_customer = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, claim, membership, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = transition_choices(claim, membership)

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        if (
            status == ReturnClaim.Status.REJECTED
            and not cleaned.get("rejection_reason", "").strip()
        ):
            self.add_error("rejection_reason", "Required when rejecting a claim.")
        if status == ReturnClaim.Status.RESOLVED:
            resolution = cleaned.get("resolution")
            if not resolution:
                self.add_error("resolution", "Choose the final resolution.")
            if not cleaned.get("resolution_summary", "").strip():
                self.add_error("resolution_summary", "Describe the final outcome.")
            if resolution in [
                ReturnClaim.Resolution.REFUNDED,
                ReturnClaim.Resolution.STORE_CREDIT,
            ] and not cleaned.get("resolution_amount"):
                self.add_error("resolution_amount", "Enter the refund or credit amount.")
            if (
                resolution == ReturnClaim.Resolution.REPLACED
                and not cleaned.get("replacement_reference", "").strip()
            ):
                self.add_error("replacement_reference", "Enter the replacement reference.")
        return cleaned
