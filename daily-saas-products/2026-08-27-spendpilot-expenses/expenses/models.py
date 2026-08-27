from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum


class Organization(models.Model):
    class Currency(models.TextChoices):
        INR = "INR", "INR — Indian rupee"
        USD = "USD", "USD — US dollar"
        EUR = "EUR", "EUR — Euro"
        GBP = "GBP", "GBP — Pound sterling"
        AUD = "AUD", "AUD — Australian dollar"

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    base_currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.INR)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        EMPLOYEE = "employee", "Employee"
        FINANCE = "finance", "Finance"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="spend_membership")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EMPLOYEE)

    @property
    def can_review(self):
        return self.role in [self.Role.OWNER, self.Role.MANAGER]

    @property
    def can_reimburse(self):
        return self.role in [self.Role.OWNER, self.Role.FINANCE]

    @property
    def can_configure(self):
        return self.role in [self.Role.OWNER, self.Role.FINANCE]

    @property
    def can_view_all(self):
        return self.role != self.Role.EMPLOYEE

    def __str__(self):
        return f"{self.user.username} · {self.get_role_display()}"


class CostCenter(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="cost_centers"
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    manager = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="managed_cost_centers",
        null=True,
        blank=True,
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="unique_spend_cost_center_code"
            )
        ]

    def clean(self):
        if (
            self.organization_id
            and self.manager_id
            and not Membership.objects.filter(
                user_id=self.manager_id, organization_id=self.organization_id
            ).exists()
        ):
            raise ValidationError({"manager": "Manager must belong to this workspace."})

    def __str__(self):
        return f"{self.code} · {self.name}"


class ExpenseCategory(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="expense_categories"
    )
    name = models.CharField(max_length=80)
    daily_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Zero disables the limit.",
    )
    receipt_required_over = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Zero disables this rule.",
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "expense categories"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_spend_category_name"
            )
        ]

    def __str__(self):
        return self.name


class ExpenseReport(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REIMBURSED = "reimbursed", "Reimbursed"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="expense_reports"
    )
    submitter = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="submitted_expense_reports"
    )
    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.PROTECT, related_name="expense_reports"
    )
    title = models.CharField(max_length=160)
    purpose = models.TextField(max_length=1500)
    trip_start = models.DateField(null=True, blank=True)
    trip_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="reviewed_expense_reports",
        null=True,
        blank=True,
    )
    decision_note = models.TextField(max_length=1200, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    reimbursed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    @property
    def reference(self):
        return f"SP-{self.pk:05d}" if self.pk else "SP-NEW"

    @property
    def total_amount(self):
        return self.items.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    @property
    def policy_issue_count(self):
        return self.items.exclude(policy_note="").count()

    @property
    def is_editable(self):
        return self.status in [self.Status.DRAFT, self.Status.REJECTED]

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.cost_center_id
            and self.cost_center.organization_id != self.organization_id
        ):
            errors["cost_center"] = "Cost center must belong to this workspace."
        if (
            self.organization_id
            and self.submitter_id
            and not Membership.objects.filter(
                user_id=self.submitter_id, organization_id=self.organization_id
            ).exists()
        ):
            errors["submitter"] = "Submitter must belong to this workspace."
        if (
            self.organization_id
            and self.reviewed_by_id
            and not Membership.objects.filter(
                user_id=self.reviewed_by_id, organization_id=self.organization_id
            ).exists()
        ):
            errors["reviewed_by"] = "Reviewer must belong to this workspace."
        if self.trip_start and self.trip_end and self.trip_end < self.trip_start:
            errors["trip_end"] = "Trip end must be on or after the start date."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.reference} · {self.title}"


class ExpenseItem(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="expense_items"
    )
    report = models.ForeignKey(ExpenseReport, on_delete=models.CASCADE, related_name="items")
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="expense_items"
    )
    expense_date = models.DateField()
    merchant = models.CharField(max_length=140)
    description = models.CharField(max_length=500, blank=True)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    receipt_url = models.URLField(blank=True)
    policy_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="spend_expense_amount_positive"
            )
        ]

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.report_id
            and self.report.organization_id != self.organization_id
        ):
            errors["report"] = "Report must belong to this workspace."
        if (
            self.organization_id
            and self.category_id
            and self.category.organization_id != self.organization_id
        ):
            errors["category"] = "Category must belong to this workspace."
        if errors:
            raise ValidationError(errors)

    def calculate_policy_note(self):
        issues = []
        if self.category_id:
            if self.category.daily_limit > 0 and self.amount > self.category.daily_limit:
                issues.append(f"exceeds {self.category.name} daily limit")
            if (
                self.category.receipt_required_over > 0
                and self.amount > self.category.receipt_required_over
                and not self.receipt_url
            ):
                issues.append("receipt required")
        if self.report_id:
            if self.report.trip_start and self.expense_date < self.report.trip_start:
                issues.append("date is before trip")
            if self.report.trip_end and self.expense_date > self.report.trip_end:
                issues.append("date is after trip")
        return "; ".join(issues)

    def save(self, *args, **kwargs):
        self.policy_note = self.calculate_policy_note()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.merchant} · {self.amount}"


class Activity(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        ITEM_ADDED = "item_added", "Item added"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REIMBURSED = "reimbursed", "Reimbursed"
        COMMENTED = "commented", "Commented"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="spend_activities"
    )
    report = models.ForeignKey(ExpenseReport, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="spend_activities")
    action = models.CharField(max_length=12, choices=Action.choices)
    message = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "activities"

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.report_id
            and self.report.organization_id != self.organization_id
        ):
            errors["report"] = "Report must belong to this workspace."
        if (
            self.organization_id
            and self.actor_id
            and not Membership.objects.filter(
                user_id=self.actor_id, organization_id=self.organization_id
            ).exists()
        ):
            errors["actor"] = "Actor must belong to this workspace."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.message
