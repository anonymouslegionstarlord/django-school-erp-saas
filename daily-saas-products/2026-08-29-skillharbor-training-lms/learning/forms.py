from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import Course, Enrollment, Membership, Module, Organization


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
        base_slug = slugify(self.cleaned_data["organization_name"]) or "workspace"
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
            department="Learning and development",
        )
        course = Course.objects.create(
            organization=organization,
            code="WELCOME",
            title="Welcome to your learning workspace",
            summary=(
                "A starter course you can edit, expand with modules, and publish to your learners."
            ),
            category=Course.Category.ONBOARDING,
            instructor=user,
            estimated_minutes=15,
            pass_mark=70,
        )
        Module.objects.create(
            organization=organization,
            course=course,
            title="Build your first course",
            order=1,
            content=(
                "Edit this module, add learning material, then publish the course "
                "and assign it to a learner."
            ),
            estimated_minutes=15,
        )
        return user


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "code",
            "title",
            "summary",
            "category",
            "level",
            "status",
            "instructor",
            "estimated_minutes",
            "pass_mark",
            "mandatory",
        ]
        widgets = {"summary": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, organization, user, **kwargs):
        super().__init__(*args, **kwargs)
        authors = User.objects.filter(
            learning_membership__organization=organization,
            learning_membership__role__in=[
                Membership.Role.OWNER,
                Membership.Role.MANAGER,
                Membership.Role.INSTRUCTOR,
            ],
        ).order_by("first_name", "username")
        membership = user.learning_membership
        if membership.role == Membership.Role.INSTRUCTOR:
            authors = authors.filter(pk=user.pk)
        self.fields["instructor"].queryset = authors
        self.fields["instructor"].initial = user

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        if status == Course.Status.PUBLISHED:
            has_modules = self.instance.pk and self.instance.modules.exists()
            if not has_modules:
                self.add_error("status", "Add at least one module before publishing.")
        return cleaned


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ["title", "order", "content", "estimated_minutes", "resource_url"]
        widgets = {"content": forms.Textarea(attrs={"rows": 8})}

    def __init__(self, *args, course, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course

    def clean_order(self):
        order = self.cleaned_data["order"]
        duplicate = Module.objects.filter(course=self.course, order=order)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("This course already has a module at that position.")
        return order


class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ["course", "learner", "due_date"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organization, user, **kwargs):
        super().__init__(*args, **kwargs)
        courses = Course.objects.filter(organization=organization, status=Course.Status.PUBLISHED)
        if user.learning_membership.role == Membership.Role.INSTRUCTOR:
            courses = courses.filter(instructor=user)
        self.fields["course"].queryset = courses
        self.fields["learner"].queryset = User.objects.filter(
            learning_membership__organization=organization,
            learning_membership__role=Membership.Role.LEARNER,
        ).order_by("first_name", "username")

    def clean(self):
        cleaned = super().clean()
        course = cleaned.get("course")
        learner = cleaned.get("learner")
        if course and learner:
            duplicate = Enrollment.objects.filter(
                organization=course.organization, course=course, learner=learner
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error("learner", "This learner is already enrolled in the course.")
        return cleaned


class ProgressForm(forms.Form):
    completed = forms.BooleanField(required=False)
    learner_note = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.TextInput(attrs={"placeholder": "Optional learning note"}),
    )


class GradeForm(forms.Form):
    score = forms.IntegerField(min_value=0, max_value=100)
    note = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Feedback for the learner"}),
    )

    def __init__(self, *args, pass_mark, **kwargs):
        super().__init__(*args, **kwargs)
        self.pass_mark = pass_mark

    def clean(self):
        cleaned = super().clean()
        score = cleaned.get("score")
        if score is not None and score < self.pass_mark and not cleaned.get("note", "").strip():
            self.add_error("note", "Add feedback when the score is below the pass mark.")
        return cleaned


class CommentForm(forms.Form):
    message = forms.CharField(
        max_length=500,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Add a coaching note or progress update"}
        ),
    )
