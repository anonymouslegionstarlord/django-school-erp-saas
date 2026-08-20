from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import Comment, Membership, Organization, Project, Task


class SignupForm(UserCreationForm):
    email = forms.EmailField()
    workspace_name = forms.CharField(max_length=120)

    class Meta:
        model = User
        fields = ("username", "email", "workspace_name", "password1", "password2")

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            base = slugify(self.cleaned_data["workspace_name"]) or "team"
            slug, suffix = base, 2
            while Organization.objects.filter(slug=slug).exists():
                slug, suffix = f"{base}-{suffix}", suffix + 1
            org = Organization.objects.create(name=self.cleaned_data["workspace_name"], slug=slug)
            Membership.objects.create(user=user, organization=org, role=Membership.Role.OWNER)
        return user


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("name", "code", "description", "color")


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ("project", "title", "description", "status", "priority", "assignee", "due_date")
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(organization=organization, archived=False)
        self.fields["assignee"].queryset = User.objects.filter(work_membership__organization=organization)


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Add context or an update…"})}
