from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import (
    Activity,
    Application,
    Candidate,
    Interview,
    JobOpening,
    Membership,
    Organization,
)


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


class JobForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = JobOpening
        fields = (
            "code",
            "title",
            "department",
            "location",
            "employment_type",
            "status",
            "openings",
            "recruiter",
            "description",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.organization = organization
        self.fields["recruiter"].queryset = User.objects.filter(
            talent_membership__organization=organization,
            talent_membership__role__in=[Membership.Role.OWNER, Membership.Role.RECRUITER],
        ).order_by("username")
        self.style_fields()


class CandidateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ("name", "email", "phone", "current_company", "source", "skills")
        widgets = {"skills": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.organization = organization
        self.style_fields()


class ApplicationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Application
        fields = ("job", "candidate", "owner", "stage", "rating", "summary")
        widgets = {"summary": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.organization = organization
        self.fields["job"].queryset = organization.job_openings.filter(
            status=JobOpening.Status.OPEN
        )
        self.fields["candidate"].queryset = organization.candidates.all()
        self.fields["owner"].queryset = User.objects.filter(
            talent_membership__organization=organization,
            talent_membership__role__in=[Membership.Role.OWNER, Membership.Role.RECRUITER],
        ).order_by("username")
        self.style_fields()


class ApplicationUpdateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Application
        fields = ("stage", "owner", "rating", "summary")
        widgets = {"summary": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.organization = organization
        self.fields["owner"].queryset = User.objects.filter(
            talent_membership__organization=organization,
            talent_membership__role__in=[Membership.Role.OWNER, Membership.Role.RECRUITER],
        ).order_by("username")
        self.style_fields()


class InterviewForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Interview
        fields = (
            "interviewer",
            "scheduled_at",
            "duration_minutes",
            "mode",
            "meeting_link",
        )
        widgets = {"scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, organization, application=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.organization = organization
        if application is not None:
            self.instance.application = application
        self.fields["interviewer"].queryset = User.objects.filter(
            talent_membership__organization=organization
        ).order_by("username")
        self.style_fields()


class InterviewFeedbackForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Interview
        fields = ("status", "score", "feedback")
        widgets = {"feedback": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == Interview.Status.COMPLETED:
            if not cleaned.get("score"):
                self.add_error("score", "Add a score when completing an interview.")
            if not cleaned.get("feedback", "").strip():
                self.add_error("feedback", "Add feedback when completing an interview.")
        return cleaned


class ActivityForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Activity
        fields = ("message",)
        widgets = {"message": forms.Textarea(attrs={"rows": 2, "placeholder": "Add a note…"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
