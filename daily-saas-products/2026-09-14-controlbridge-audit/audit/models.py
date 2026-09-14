import secrets

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):  # noqa: DJ012
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        MANAGER = "MANAGER", "Audit manager"
        ANALYST = "ANALYST", "Auditor"
        VIEWER = "VIEWER", "Viewer"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="audit_membership")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=12, choices=Role.choices)

    @property
    def can_manage(self):
        return self.role in {self.Role.OWNER, self.Role.MANAGER}

    @property
    def can_work(self):
        return self.role != self.Role.VIEWER

    def __str__(self):  # noqa: DJ012
        return f"{self.user} · {self.get_role_display()}"


class ControlArea(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="control_areas")
    name = models.CharField(max_length=120)
    email = models.EmailField()
    department = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "email"], name="unique_control_area_email_per_org")]
        ordering = ["name"]

    def __str__(self):  # noqa: DJ012
        return f"{self.name} <{self.email}>"


class AuditFinding(models.Model):
    class Kind(models.TextChoices):
        CONTROL_GAP = "CONTROL_GAP", "Control gap"
        POLICY_BREACH = "POLICY_BREACH", "Policy breach"
        ACCESS_RISK = "ACCESS_RISK", "Access risk"
        EVIDENCE_GAP = "EVIDENCE_GAP", "Evidence gap"
        THIRD_PARTY_RISK = "THIRD_PARTY_RISK", "Third-party risk"

    class Framework(models.TextChoices):
        SOX = "SOX", "SOX"
        ISO27001 = "ISO27001", "ISO 27001"
        SOC2 = "SOC2", "SOC 2"
        PCI_DSS = "PCI_DSS", "PCI DSS"
        INTERNAL = "INTERNAL", "Internal policy"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        TRIAGE = "TRIAGE", "Triage"
        REMEDIATION = "REMEDIATION", "Remediation"
        REVIEW = "REVIEW", "Final review"
        RESOLVED = "RESOLVED", "Resolved"
        ACCEPTED_RISK = "ACCEPTED_RISK", "Risk accepted"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="findings")
    tracking_code = models.CharField(max_length=24, unique=True, editable=False)
    control_area = models.ForeignKey(ControlArea, on_delete=models.PROTECT, related_name="findings")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    framework = models.CharField(max_length=16, choices=Framework.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    description = models.TextField()
    received_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField()
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_assignments")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="audit_findings_created")
    triaged_at = models.DateTimeField(null=True, blank=True)
    resolution_summary = models.TextField(blank=True)
    evidence_reference = models.CharField(max_length=120, blank=True)
    risk_acceptance_reason = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_at", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.tracking_code:
            self.tracking_code = f"AUD-{secrets.token_hex(5).upper()}"
        super().save(*args, **kwargs)

    def __str__(self):  # noqa: DJ012
        return f"{self.tracking_code} · {self.control_area.name}"

    def clean(self):
        errors = {}
        if self.control_area_id and self.control_area.organization_id != self.organization_id:
            errors["control_area"] = "Control area must belong to this workspace."
        if self.assigned_to_id:
            membership = getattr(self.assigned_to, "audit_membership", None)
            if not membership or membership.organization_id != self.organization_id:
                errors["assigned_to"] = "Assignee must belong to this workspace."
        if self.status == self.Status.RESOLVED and not (self.resolution_summary and self.evidence_reference):
            errors["resolution_summary"] = "Resolution requires a summary and evidence reference."
        if self.status == self.Status.ACCEPTED_RISK and not self.risk_acceptance_reason:
            errors["risk_acceptance_reason"] = "A rejection reason is required."
        if errors:
            raise ValidationError(errors)

    @property
    def is_overdue(self):
        return not self.completed_at and self.due_at < timezone.now()

    @property
    def days_remaining(self):
        return (self.due_at.date() - timezone.localdate()).days


class RemediationTask(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        WORKING = "WORKING", "Working"
        DONE = "DONE", "Done"

    finding = models.ForeignKey(AuditFinding, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=160)
    assignee = models.ForeignKey(User, on_delete=models.PROTECT, related_name="audit_tasks")
    due_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        membership = getattr(self.assignee, "audit_membership", None)
        if not membership or membership.organization_id != self.finding.organization_id:
            raise ValidationError({"assignee": "Assignee must belong to this workspace."})

    def __str__(self):  # noqa: DJ012
        return f"{self.finding.tracking_code} · {self.title}"

    @property
    def is_overdue(self):
        return self.status != self.Status.DONE and self.due_at < timezone.now()


class FindingEvent(models.Model):
    finding = models.ForeignKey(AuditFinding, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    message = models.CharField(max_length=240)
    visible_to_stakeholders = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.finding.tracking_code} · {self.message[:40]}"
