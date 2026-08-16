from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class School(TimeStampedModel):
    class Plan(models.TextChoices):
        STARTER = "starter", "Starter"
        GROWTH = "growth", "Growth"
        PRO = "pro", "Pro"

    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=24, blank=True)
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.STARTER)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Administrator"
        TEACHER = "teacher", "Teacher"
        ACCOUNTANT = "accountant", "Accountant"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="school_memberships")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TEACHER)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "school"], name="unique_school_membership")]

    def __str__(self):
        return f"{self.user} · {self.school} · {self.get_role_display()}"


class Student(TimeStampedModel):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="students")
    admission_number = models.CharField(max_length=30)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    guardian_name = models.CharField(max_length=160)
    guardian_phone = models.CharField(max_length=24)
    class_name = models.CharField("class", max_length=40)
    section = models.CharField(max_length=10, blank=True)
    enrolled_on = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "admission_number"], name="unique_school_admission_number")
        ]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.full_name} ({self.admission_number})"


class Teacher(TimeStampedModel):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="teachers")
    employee_id = models.CharField(max_length=30)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_profiles",
    )
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    email = models.EmailField()
    subject = models.CharField(max_length=100)
    joined_on = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        constraints = [models.UniqueConstraint(fields=["school", "employee_id"], name="unique_school_employee_id")]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.full_name


class Course(TimeStampedModel):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="courses")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=120)
    grade_level = models.CharField(max_length=40)
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name="courses")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["grade_level", "name"]
        constraints = [models.UniqueConstraint(fields=["school", "code"], name="unique_school_course_code")]

    def __str__(self):
        return f"{self.code} · {self.name}"


class Enrollment(TimeStampedModel):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="enrollments")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "course"], name="unique_course_enrollment")]

    def __str__(self):
        return f"{self.student} → {self.course}"


class Attendance(TimeStampedModel):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"
        EXCUSED = "excused", "Excused"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="attendance_records")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance_records")
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_records"
    )
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT)
    notes = models.CharField(max_length=255, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_attendance",
    )

    class Meta:
        ordering = ["-date", "student__first_name"]
        constraints = [models.UniqueConstraint(fields=["school", "student", "date"], name="daily_student_attendance")]

    def __str__(self):
        return f"{self.student} · {self.date} · {self.get_status_display()}"


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIAL = "partial", "Partially paid"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="invoices")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="invoices")
    title = models.CharField(max_length=140)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-due_date", "student__first_name"]

    @property
    def paid_amount(self):
        return self.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    @property
    def balance(self):
        return max(self.amount - self.paid_amount, Decimal("0.00"))

    def refresh_status(self):
        paid = self.paid_amount
        if paid >= self.amount:
            next_status = self.Status.PAID
        elif paid > 0:
            next_status = self.Status.PARTIAL
        elif self.due_date < timezone.localdate():
            next_status = self.Status.OVERDUE
        else:
            next_status = self.Status.PENDING
        if self.status != next_status:
            self.status = next_status
            self.save(update_fields=["status", "updated_at"])

    def __str__(self):
        return f"{self.student} · {self.title}"


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        UPI = "upi", "UPI"
        CARD = "card", "Card"
        BANK = "bank", "Bank transfer"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.UPI)
    reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_payments",
    )

    class Meta:
        ordering = ["-paid_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.refresh_status()

    def __str__(self):
        return f"₹{self.amount} for {self.invoice}"
