from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.text import slugify

from .models import (
    Customer,
    DriverProfile,
    Membership,
    Organization,
    Shipment,
    Vehicle,
)
from .services import transition_choices


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"


class DateInput(forms.DateInput):
    input_type = "date"


class SignupForm(UserCreationForm):
    workspace_name = forms.CharField(max_length=140, help_text="Your delivery operation name")
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
                title="Operations owner",
            )
        return user


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "contact_name", "email", "phone", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            "registration",
            "name",
            "kind",
            "capacity_kg",
            "status",
            "odometer_km",
            "next_service_km",
        ]

    def clean_registration(self):
        return self.cleaned_data["registration"].strip().upper()


class DriverCreateForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    temporary_password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    license_number = forms.CharField(max_length=64)
    license_expiry = forms.DateField(widget=DateInput())
    phone = forms.CharField(max_length=32)

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("That username is already in use.")
        return username

    def clean_license_number(self):
        number = self.cleaned_data["license_number"].strip().upper()
        if DriverProfile.objects.filter(
            organization=self.organization, license_number__iexact=number
        ).exists():
            raise ValidationError("That license number already exists in this workspace.")
        return number

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
            role=Membership.Role.DRIVER,
            title="Delivery driver",
        )
        driver = DriverProfile(
            organization=self.organization,
            user=user,
            license_number=self.cleaned_data["license_number"],
            license_expiry=self.cleaned_data["license_expiry"],
            phone=self.cleaned_data["phone"],
        )
        driver.full_clean()
        driver.save()
        return driver


class ShipmentForm(forms.ModelForm):
    class Meta:
        model = Shipment
        fields = [
            "tracking_code",
            "customer",
            "pickup_address",
            "delivery_address",
            "package_description",
            "weight_kg",
            "priority",
            "scheduled_pickup",
            "delivery_deadline",
        ]
        widgets = {
            "pickup_address": forms.Textarea(attrs={"rows": 3}),
            "delivery_address": forms.Textarea(attrs={"rows": 3}),
            "scheduled_pickup": DateTimeInput(format="%Y-%m-%dT%H:%M"),
            "delivery_deadline": DateTimeInput(format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(organization=organization)
        self.fields["scheduled_pickup"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["delivery_deadline"].input_formats = ["%Y-%m-%dT%H:%M"]

    def clean_tracking_code(self):
        return self.cleaned_data["tracking_code"].strip().upper()


class AssignmentForm(forms.Form):
    driver = forms.ModelChoiceField(queryset=DriverProfile.objects.none())
    vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.none())

    def __init__(self, *args, organization, shipment, **kwargs):
        super().__init__(*args, **kwargs)
        current = getattr(shipment, "assignment", None)
        driver_ids = []
        vehicle_ids = []
        if current:
            driver_ids.append(current.driver_id)
            vehicle_ids.append(current.vehicle_id)
        self.fields["driver"].queryset = DriverProfile.objects.filter(
            organization=organization,
            status__in=[DriverProfile.Status.AVAILABLE, DriverProfile.Status.ON_ROUTE],
        ).filter(models.Q(status=DriverProfile.Status.AVAILABLE) | models.Q(pk__in=driver_ids))
        self.fields["vehicle"].queryset = Vehicle.objects.filter(
            organization=organization, capacity_kg__gte=shipment.weight_kg
        ).filter(models.Q(status=Vehicle.Status.AVAILABLE) | models.Q(pk__in=vehicle_ids))


class TransitionForm(forms.Form):
    status = forms.ChoiceField(choices=[])
    update_message = forms.CharField(
        max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    delivery_reference = forms.CharField(max_length=120, required=False)
    proof_note = forms.CharField(
        max_length=1000, required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    failure_reason = forms.CharField(
        max_length=1000, required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    visible_to_customer = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, shipment, membership, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = transition_choices(shipment, membership)

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        if status == Shipment.Status.DELIVERED:
            if not cleaned.get("delivery_reference", "").strip():
                self.add_error("delivery_reference", "Required for a delivered shipment.")
            if not cleaned.get("proof_note", "").strip():
                self.add_error("proof_note", "Required for a delivered shipment.")
        if status == Shipment.Status.FAILED and not cleaned.get("failure_reason", "").strip():
            self.add_error("failure_reason", "Required when delivery fails.")
        return cleaned
