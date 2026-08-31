from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    name = models.CharField(max_length=140)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        RISK_MANAGER = "risk_manager", "Risk manager"
        ANALYST = "analyst", "Risk analyst"
        VIEWER = "viewer", "Viewer"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="vendor_risk_membership"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=14, choices=Role.choices, default=Role.VIEWER)
    team = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f"{self.user.username} · {self.get_role_display()}"

    @property
    def can_manage(self):
        return self.role in [self.Role.OWNER, self.Role.RISK_MANAGER]

    @property
    def can_assess(self):
        return self.role in [
            self.Role.OWNER,
            self.Role.RISK_MANAGER,
            self.Role.ANALYST,
        ]


class Vendor(models.Model):
    class Category(models.TextChoices):
        CLOUD = "cloud", "Cloud and infrastructure"
        DATA = "data", "Data and analytics"
        FINANCE = "finance", "Finance and payments"
        PROFESSIONAL = "professional", "Professional services"
        OTHER = "other", "Other"

    class Criticality(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        ONBOARDING = "onboarding", "Onboarding"
        ACTIVE = "active", "Active"
        UNDER_REVIEW = "under_review", "Under review"
        SUSPENDED = "suspended", "Suspended"
        OFFBOARDED = "offboarded", "Offboarded"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="vendors")
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160)
    category = models.CharField(max_length=16, choices=Category.choices)
    criticality = models.CharField(
        max_length=10, choices=Criticality.choices, default=Criticality.MEDIUM
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ONBOARDING)
    service_description = models.TextField(max_length=1800)
    business_owner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="owned_risk_vendors"
    )
    handles_personal_data = models.BooleanField(default=False)
    has_production_access = models.BooleanField(default=False)
    has_financial_access = models.BooleanField(default=False)
    annual_spend = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    contract_expiry = models.DateField(null=True, blank=True)
    next_review = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criticality", "name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "slug"], name="unique_vendor_risk_slug")
        ]

    def __str__(self):
        return self.name

    @property
    def latest_assessment(self):
        return self.assessments.filter(status=Assessment.Status.COMPLETED).first()

    @property
    def risk_rating(self):
        assessment = self.latest_assessment
        return assessment.risk_rating if assessment else "unassessed"

    @property
    def is_review_due(self):
        return bool(self.next_review and self.next_review <= timezone.localdate())

    @property
    def exposure_count(self):
        return sum(
            [
                self.handles_personal_data,
                self.has_production_access,
                self.has_financial_access,
            ]
        )

    def clean(self):
        if (
            self.organization_id
            and self.business_owner_id
            and not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.business_owner_id
            ).exists()
        ):
            raise ValidationError(
                {"business_owner": "Business owner must belong to this workspace."}
            )


class Assessment(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In review"
        COMPLETED = "completed", "Completed"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="assessments"
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="assessments")
    title = models.CharField(max_length=180)
    scope = models.TextField(max_length=1800)
    assessor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="vendor_assessments")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    due_date = models.DateField()
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.vendor.name} · {self.title}"

    @property
    def control_count(self):
        return self.controls.count()

    @property
    def answered_controls(self):
        return self.controls.exclude(response=AssessmentControl.Response.UNANSWERED).count()

    @property
    def progress_percent(self):
        return round(self.answered_controls / self.control_count * 100) if self.control_count else 0

    @property
    def score(self):
        controls = list(
            self.controls.exclude(response=AssessmentControl.Response.UNANSWERED).exclude(
                response=AssessmentControl.Response.NOT_APPLICABLE
            )
        )
        maximum = sum(control.weight * 20 for control in controls)
        if not maximum:
            return None
        return round(sum(control.risk_points for control in controls) / maximum * 100)

    @property
    def risk_rating(self):
        score = self.score
        if score is None:
            return "unassessed"
        if score >= 75:
            return "critical"
        if score >= 50:
            return "high"
        if score >= 25:
            return "moderate"
        return "low"

    @property
    def is_overdue(self):
        return self.status != self.Status.COMPLETED and self.due_date < timezone.localdate()

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.vendor_id
            and self.vendor.organization_id != self.organization_id
        ):
            errors["vendor"] = "Vendor must belong to this workspace."
        if self.organization_id and self.assessor_id:
            membership = Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.assessor_id
            ).first()
            if membership is None or not membership.can_assess:
                errors["assessor"] = "Assessor must have assessment access in this workspace."
        if self.status == self.Status.COMPLETED and not self.completed_at:
            errors["completed_at"] = "Completed assessments require a completion timestamp."
        if errors:
            raise ValidationError(errors)


class AssessmentControl(models.Model):
    class Domain(models.TextChoices):
        SECURITY = "security", "Security"
        PRIVACY = "privacy", "Privacy"
        RESILIENCE = "resilience", "Resilience"
        COMPLIANCE = "compliance", "Compliance"
        GOVERNANCE = "governance", "Governance"

    class Response(models.TextChoices):
        UNANSWERED = "", "Unanswered"
        YES = "yes", "Implemented"
        PARTIAL = "partial", "Partially implemented"
        NO = "no", "Not implemented"
        NOT_APPLICABLE = "na", "Not applicable"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="assessment_controls"
    )
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="controls")
    domain = models.CharField(max_length=12, choices=Domain.choices)
    question = models.CharField(max_length=320)
    weight = models.PositiveSmallIntegerField(default=3)
    response = models.CharField(
        max_length=8, choices=Response.choices, blank=True, default=Response.UNANSWERED
    )
    evidence = models.URLField(blank=True)
    notes = models.TextField(max_length=1800, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.get_domain_display()} · {self.question[:60]}"

    @property
    def risk_points(self):
        multiplier = {
            self.Response.YES: 0,
            self.Response.PARTIAL: 10,
            self.Response.NO: 20,
            self.Response.NOT_APPLICABLE: 0,
            self.Response.UNANSWERED: 0,
        }[self.response]
        return self.weight * multiplier

    def clean(self):
        if (
            self.organization_id
            and self.assessment_id
            and self.assessment.organization_id != self.organization_id
        ):
            raise ValidationError({"assessment": "Assessment must belong to this workspace."})
        if not 1 <= self.weight <= 5:
            raise ValidationError({"weight": "Control weight must be between 1 and 5."})


class Finding(models.Model):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        ACCEPTED = "accepted", "Risk accepted"
        RESOLVED = "resolved", "Resolved"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="findings"
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="findings")
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="findings")
    title = models.CharField(max_length=220)
    description = models.TextField(max_length=2200)
    severity = models.CharField(max_length=8, choices=Severity.choices)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="risk_findings")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    due_date = models.DateField(null=True, blank=True)
    resolution_notes = models.TextField(max_length=1800, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-severity", "due_date"]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return bool(
            self.due_date
            and self.due_date < timezone.localdate()
            and self.status not in [self.Status.RESOLVED, self.Status.ACCEPTED]
        )

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.vendor_id
            and self.vendor.organization_id != self.organization_id
        ):
            errors["vendor"] = "Vendor must belong to this workspace."
        if (
            self.organization_id
            and self.assessment_id
            and self.assessment.organization_id != self.organization_id
        ):
            errors["assessment"] = "Assessment must belong to this workspace."
        if self.vendor_id and self.assessment_id and self.assessment.vendor_id != self.vendor_id:
            errors["assessment"] = "Assessment must belong to the selected vendor."
        if (
            self.organization_id
            and self.owner_id
            and not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.owner_id
            ).exists()
        ):
            errors["owner"] = "Finding owner must belong to this workspace."
        if self.status == self.Status.RESOLVED and not self.resolution_notes.strip():
            errors["resolution_notes"] = "Resolution notes are required."
        if self.status == self.Status.RESOLVED and not self.resolved_at:
            errors["resolved_at"] = "Resolved findings require a timestamp."
        if errors:
            raise ValidationError(errors)


class Activity(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="risk_activity"
    )
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="risk_activity")
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="activity")
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="activity",
        null=True,
        blank=True,
    )
    message = models.CharField(max_length=320)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.vendor_id
            and self.vendor.organization_id != self.organization_id
        ):
            errors["vendor"] = "Vendor must belong to this workspace."
        if (
            self.organization_id
            and self.actor_id
            and not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.actor_id
            ).exists()
        ):
            errors["actor"] = "Actor must belong to this workspace."
        if (
            self.organization_id
            and self.assessment_id
            and self.assessment.organization_id != self.organization_id
        ):
            errors["assessment"] = "Assessment must belong to this workspace."
        if self.vendor_id and self.assessment_id and self.assessment.vendor_id != self.vendor_id:
            errors["assessment"] = "Assessment must belong to the selected vendor."
        if errors:
            raise ValidationError(errors)
