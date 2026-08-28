from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        LEAD = "lead", "QA lead"
        TESTER = "tester", "Tester"
        VIEWER = "viewer", "Viewer"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="quality_membership")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=8, choices=Role.choices, default=Role.TESTER)

    @property
    def can_manage(self):
        return self.role in [self.Role.OWNER, self.Role.LEAD]

    @property
    def can_execute(self):
        return self.role in [self.Role.OWNER, self.Role.LEAD, self.Role.TESTER]

    def __str__(self):
        return f"{self.user.username} · {self.get_role_display()}"


class Product(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        MAINTENANCE = "maintenance", "Maintenance"
        ARCHIVED = "archived", "Archived"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="products"
    )
    key = models.CharField(max_length=12)
    name = models.CharField(max_length=140)
    description = models.TextField(max_length=1500, blank=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_qa_products")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "key"], name="unique_quality_product_key"
            )
        ]

    def clean(self):
        if (
            self.organization_id
            and self.owner_id
            and not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.owner_id
            ).exists()
        ):
            raise ValidationError({"owner": "Product owner must belong to this workspace."})

    def __str__(self):
        return f"{self.key} · {self.name}"


class TestSuite(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="test_suites"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="test_suites")
    name = models.CharField(max_length=120)
    description = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["product__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "product", "name"],
                name="unique_quality_suite_name",
            )
        ]

    def clean(self):
        if (
            self.organization_id
            and self.product_id
            and self.product.organization_id != self.organization_id
        ):
            raise ValidationError({"product": "Product must belong to this workspace."})

    def __str__(self):
        return f"{self.product.key} · {self.name}"


class TestCase(models.Model):
    class Priority(models.TextChoices):
        CRITICAL = "critical", "Critical"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    class TestType(models.TextChoices):
        FUNCTIONAL = "functional", "Functional"
        REGRESSION = "regression", "Regression"
        SMOKE = "smoke", "Smoke"
        INTEGRATION = "integration", "Integration"
        USABILITY = "usability", "Usability"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        DEPRECATED = "deprecated", "Deprecated"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="test_cases"
    )
    suite = models.ForeignKey(TestSuite, on_delete=models.PROTECT, related_name="test_cases")
    case_key = models.CharField(max_length=24)
    title = models.CharField(max_length=180)
    requirement_reference = models.CharField(max_length=80, blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    test_type = models.CharField(
        max_length=12, choices=TestType.choices, default=TestType.FUNCTIONAL
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    preconditions = models.TextField(max_length=2000, blank=True)
    steps = models.TextField(max_length=5000)
    expected_result = models.TextField(max_length=2500)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_test_cases"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["case_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "case_key"], name="unique_quality_case_key"
            )
        ]

    @property
    def product(self):
        return self.suite.product

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.suite_id
            and self.suite.organization_id != self.organization_id
        ):
            errors["suite"] = "Suite must belong to this workspace."
        if (
            self.organization_id
            and self.created_by_id
            and not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.created_by_id
            ).exists()
        ):
            errors["created_by"] = "Author must belong to this workspace."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.case_key} · {self.title}"


class TestRun(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    class Environment(models.TextChoices):
        LOCAL = "local", "Local"
        QA = "qa", "QA"
        STAGING = "staging", "Staging"
        PRODUCTION = "production", "Production"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="test_runs"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="test_runs")
    name = models.CharField(max_length=180)
    target_version = models.CharField(max_length=60)
    environment = models.CharField(
        max_length=12, choices=Environment.choices, default=Environment.STAGING
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANNED)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_test_runs")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def reference(self):
        return f"RUN-{self.pk:04d}" if self.pk else "RUN-NEW"

    @property
    def total_count(self):
        return self.executions.count()

    @property
    def executed_count(self):
        return self.executions.exclude(status=TestExecution.Status.NOT_RUN).count()

    @property
    def passed_count(self):
        return self.executions.filter(status=TestExecution.Status.PASSED).count()

    @property
    def not_run_count(self):
        return self.executions.filter(status=TestExecution.Status.NOT_RUN).count()

    @property
    def failed_count(self):
        return self.executions.filter(status=TestExecution.Status.FAILED).count()

    @property
    def blocked_count(self):
        return self.executions.filter(status=TestExecution.Status.BLOCKED).count()

    @property
    def completion_rate(self):
        return round(self.executed_count * 100 / self.total_count) if self.total_count else 0

    @property
    def pass_rate(self):
        return round(self.passed_count * 100 / self.executed_count) if self.executed_count else 0

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.product_id
            and self.product.organization_id != self.organization_id
        ):
            errors["product"] = "Product must belong to this workspace."
        if (
            self.organization_id
            and self.created_by_id
            and not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.created_by_id
            ).exists()
        ):
            errors["created_by"] = "Creator must belong to this workspace."
        if self.start_date and self.due_date and self.due_date < self.start_date:
            errors["due_date"] = "Due date must be on or after the start date."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.reference} · {self.name}"


class TestExecution(models.Model):
    class Status(models.TextChoices):
        NOT_RUN = "not_run", "Not run"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"
        BLOCKED = "blocked", "Blocked"
        SKIPPED = "skipped", "Skipped"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="test_executions"
    )
    run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name="executions")
    test_case = models.ForeignKey(TestCase, on_delete=models.PROTECT, related_name="executions")
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="assigned_test_executions",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NOT_RUN)
    actual_result = models.TextField(max_length=2500, blank=True)
    defect_reference = models.CharField(max_length=180, blank=True)
    evidence_url = models.URLField(blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["test_case__case_key"]
        constraints = [
            models.UniqueConstraint(fields=["run", "test_case"], name="unique_quality_case_per_run")
        ]

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.run_id
            and self.run.organization_id != self.organization_id
        ):
            errors["run"] = "Run must belong to this workspace."
        if (
            self.organization_id
            and self.test_case_id
            and self.test_case.organization_id != self.organization_id
        ):
            errors["test_case"] = "Test case must belong to this workspace."
        if (
            self.run_id
            and self.test_case_id
            and self.run.product_id != self.test_case.suite.product_id
        ):
            errors["test_case"] = "Test case must belong to the run product."
        if (
            self.organization_id
            and self.assigned_to_id
            and not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.assigned_to_id
            ).exists()
        ):
            errors["assigned_to"] = "Assignee must belong to this workspace."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.status == self.Status.NOT_RUN:
            self.executed_at = None
        elif self.executed_at is None:
            self.executed_at = timezone.now()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.run.reference} · {self.test_case.case_key}"


class Activity(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="quality_activities"
    )
    run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="quality_activities")
    message = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "activities"

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.run_id
            and self.run.organization_id != self.organization_id
        ):
            errors["run"] = "Run must belong to this workspace."
        if (
            self.organization_id
            and self.actor_id
            and not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.actor_id
            ).exists()
        ):
            errors["actor"] = "Actor must belong to this workspace."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.message
