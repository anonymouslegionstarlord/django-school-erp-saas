from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import Attendance, Course, Invoice, Membership, Payment, School, Student, Teacher


class StyledFormMixin:
    def _style_fields(self):
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class SchoolSignUpForm(StyledFormMixin, UserCreationForm):
    first_name = forms.CharField(max_length=80)
    last_name = forms.CharField(max_length=80)
    email = forms.EmailField()
    school_name = forms.CharField(max_length=160, help_text="Your school or academy name")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "school_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if not commit:
            return user
        user.save()
        base_slug = slugify(self.cleaned_data["school_name"]) or "school"
        slug = base_slug
        suffix = 2
        while School.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        school = School.objects.create(name=self.cleaned_data["school_name"], slug=slug, email=user.email)
        Membership.objects.create(user=user, school=school, role=Membership.Role.OWNER)
        return user


class TenantModelForm(StyledFormMixin, forms.ModelForm):
    def __init__(self, *args, school=None, **kwargs):
        self.school = school
        super().__init__(*args, **kwargs)
        self._style_fields()

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.school = self.school
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class StudentForm(TenantModelForm):
    class Meta:
        model = Student
        exclude = ("school",)
        widgets = {"enrolled_on": forms.DateInput(attrs={"type": "date"})}


class TeacherForm(TenantModelForm):
    class Meta:
        model = Teacher
        exclude = ("school", "user")
        widgets = {"joined_on": forms.DateInput(attrs={"type": "date"})}


class CourseForm(TenantModelForm):
    class Meta:
        model = Course
        exclude = ("school",)

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, school=school, **kwargs)
        self.fields["teacher"].queryset = Teacher.objects.filter(school=school, is_active=True)


class AttendanceForm(TenantModelForm):
    class Meta:
        model = Attendance
        exclude = ("school", "marked_by")
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, school=school, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(school=school, is_active=True)
        self.fields["course"].queryset = Course.objects.filter(school=school, is_active=True)


class InvoiceForm(TenantModelForm):
    class Meta:
        model = Invoice
        exclude = ("school", "status")
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, school=school, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(school=school, is_active=True)


class PaymentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Payment
        fields = ("amount", "method", "reference", "paid_at")
        widgets = {"paid_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
