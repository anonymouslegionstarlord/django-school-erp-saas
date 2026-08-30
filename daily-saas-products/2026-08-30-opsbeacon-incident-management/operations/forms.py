from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import (
    ActionItem,
    Incident,
    IncidentResponder,
    Membership,
    Organization,
    Service,
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
        base_slug = slugify(self.cleaned_data["organization_name"]) or "status"
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
            team="Operations",
        )
        Service.objects.create(
            organization=organization,
            name="Customer platform",
            slug="customer-platform",
            description="Edit this service or add the systems your team operates.",
            owner=user,
        )
        return user


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "slug", "description", "status", "owner", "public"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["owner"].queryset = User.objects.filter(
            operations_membership__organization=organization,
            operations_membership__role__in=[
                Membership.Role.OWNER,
                Membership.Role.COMMANDER,
                Membership.Role.RESPONDER,
            ],
        ).order_by("first_name", "username")

    def clean_slug(self):
        slug = slugify(self.cleaned_data["slug"])
        duplicate = Service.objects.filter(organization=self.organization, slug=slug)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("A service already uses this status-page slug.")
        return slug


class IncidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = [
            "service",
            "title",
            "severity",
            "summary",
            "customer_impact",
            "commander",
            "started_at",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 5}),
            "customer_impact": forms.Textarea(attrs={"rows": 4}),
            "started_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = Service.objects.filter(organization=organization)
        self.fields["commander"].queryset = User.objects.filter(
            operations_membership__organization=organization,
            operations_membership__role__in=[
                Membership.Role.OWNER,
                Membership.Role.COMMANDER,
                Membership.Role.RESPONDER,
            ],
        ).order_by("first_name", "username")


class IncidentUpdateForm(forms.Form):
    ALLOWED_TRANSITIONS = {
        Incident.Status.INVESTIGATING: [
            Incident.Status.IDENTIFIED,
            Incident.Status.MONITORING,
            Incident.Status.RESOLVED,
        ],
        Incident.Status.IDENTIFIED: [
            Incident.Status.MONITORING,
            Incident.Status.RESOLVED,
        ],
        Incident.Status.MONITORING: [
            Incident.Status.INVESTIGATING,
            Incident.Status.RESOLVED,
        ],
        Incident.Status.RESOLVED: [],
    }

    status = forms.ChoiceField(choices=Incident.Status.choices)
    message = forms.CharField(
        max_length=1800,
        widget=forms.Textarea(
            attrs={"rows": 4, "placeholder": "What changed, and what happens next?"}
        ),
    )
    public = forms.BooleanField(
        required=False, help_text="Show this update on the public status page."
    )
    resolution_summary = forms.CharField(
        required=False,
        max_length=2500,
        widget=forms.Textarea(
            attrs={"rows": 4, "placeholder": "Root cause and how service was restored"}
        ),
    )

    def __init__(self, *args, incident, **kwargs):
        super().__init__(*args, **kwargs)
        self.incident = incident
        allowed = [incident.status, *self.ALLOWED_TRANSITIONS[incident.status]]
        labels = dict(Incident.Status.choices)
        self.fields["status"].choices = [(value, labels[value]) for value in allowed]
        self.fields["status"].initial = incident.status

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        allowed = [self.incident.status, *self.ALLOWED_TRANSITIONS[self.incident.status]]
        if status and status not in allowed:
            self.add_error("status", "That incident transition is not allowed.")
        if status == Incident.Status.RESOLVED and not cleaned.get("resolution_summary", "").strip():
            self.add_error("resolution_summary", "Explain how the incident was resolved.")
        return cleaned


class ResponderForm(forms.ModelForm):
    class Meta:
        model = IncidentResponder
        fields = ["user", "responsibility"]

    def __init__(self, *args, organization, incident, **kwargs):
        super().__init__(*args, **kwargs)
        self.incident = incident
        self.fields["user"].queryset = User.objects.filter(
            operations_membership__organization=organization,
            operations_membership__role__in=[
                Membership.Role.OWNER,
                Membership.Role.COMMANDER,
                Membership.Role.RESPONDER,
            ],
        ).exclude(pk__in=incident.responders.values_list("user_id", flat=True))


class ActionItemForm(forms.ModelForm):
    class Meta:
        model = ActionItem
        fields = ["title", "owner", "due_date"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = User.objects.filter(
            operations_membership__organization=organization
        ).order_by("first_name", "username")
