from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import AuditFinding, ControlArea, Membership, Organization, RemediationTask


class SignupForm(UserCreationForm):
    organization_name = forms.CharField(max_length=120)
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "organization_name")

    def save(self, commit=True):
        from django.utils.text import slugify

        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            root = slugify(self.cleaned_data["organization_name"]) or "workspace"
            slug, index = root, 2
            while Organization.objects.filter(slug=slug).exists():
                slug, index = f"{root}-{index}", index + 1
            org = Organization.objects.create(name=self.cleaned_data["organization_name"], slug=slug)
            Membership.objects.create(user=user, organization=org, role=Membership.Role.OWNER)
        return user


class ControlAreaForm(forms.ModelForm):
    class Meta:
        model = ControlArea
        fields = ["name", "email", "department"]


class RequestForm(forms.ModelForm):
    class Meta:
        model = AuditFinding
        fields = ["control_area", "kind", "framework", "description", "due_at", "assigned_to"]
        widgets = {"due_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["control_area"].queryset = organization.control_areas.all()
        self.fields["assigned_to"].queryset = User.objects.filter(
            audit_membership__organization=organization,
            audit_membership__role__in=[Membership.Role.OWNER, Membership.Role.MANAGER, Membership.Role.ANALYST],
        )
        if not self.is_bound:
            self.initial["due_at"] = timezone.now() + timezone.timedelta(days=30)


class TaskForm(forms.ModelForm):
    class Meta:
        model = RemediationTask
        fields = ["title", "assignee", "due_at", "notes"]
        widgets = {"due_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = User.objects.filter(audit_membership__organization=organization).exclude(
            audit_membership__role=Membership.Role.VIEWER
        )
