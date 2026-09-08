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
        MANAGER = "MANAGER", "Privacy manager"
        ANALYST = "ANALYST", "Analyst"
        VIEWER = "VIEWER", "Viewer"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="privacy_membership")
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


class DataSubject(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="subjects")
    name = models.CharField(max_length=120)
    email = models.EmailField()
    country = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "email"], name="unique_subject_email_per_org")]
        ordering = ["name"]

    def __str__(self):  # noqa: DJ012
        return f"{self.name} <{self.email}>"


class PrivacyRequest(models.Model):
    class Kind(models.TextChoices):
        ACCESS = "ACCESS", "Access"
        DELETION = "DELETION", "Deletion"
        CORRECTION = "CORRECTION", "Correction"
        PORTABILITY = "PORTABILITY", "Portability"
        OBJECTION = "OBJECTION", "Objection"

    class Jurisdiction(models.TextChoices):
        GDPR = "GDPR", "EU GDPR"
        UK_GDPR = "UK_GDPR", "UK GDPR"
        CCPA = "CCPA", "California CCPA"
        INDIA_DPDP = "INDIA_DPDP", "India DPDP"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        VERIFYING = "VERIFYING", "Verifying identity"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        REVIEW = "REVIEW", "Final review"
        FULFILLED = "FULFILLED", "Fulfilled"
        REJECTED = "REJECTED", "Rejected"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="requests")
    tracking_code = models.CharField(max_length=24, unique=True, editable=False)
    subject = models.ForeignKey(DataSubject, on_delete=models.PROTECT, related_name="requests")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    jurisdiction = models.CharField(max_length=16, choices=Jurisdiction.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED)
    description = models.TextField()
    received_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField()
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="privacy_assignments")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="privacy_requests_created")
    identity_verified_at = models.DateTimeField(null=True, blank=True)
    resolution_summary = models.TextField(blank=True)
    secure_delivery_reference = models.CharField(max_length=120, blank=True)
    rejection_reason = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_at", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.tracking_code:
            self.tracking_code = f"DSR-{secrets.token_hex(5).upper()}"
        super().save(*args, **kwargs)

    def __str__(self):  # noqa: DJ012
        return f"{self.tracking_code} · {self.subject.name}"

    def clean(self):
        errors = {}
        if self.subject_id and self.subject.organization_id != self.organization_id:
            errors["subject"] = "Subject must belong to this workspace."
        if self.assigned_to_id:
            membership = getattr(self.assigned_to, "privacy_membership", None)
            if not membership or membership.organization_id != self.organization_id:
                errors["assigned_to"] = "Assignee must belong to this workspace."
        if self.status == self.Status.FULFILLED and not (self.resolution_summary and self.secure_delivery_reference):
            errors["resolution_summary"] = "Fulfilment requires a summary and secure delivery reference."
        if self.status == self.Status.REJECTED and not self.rejection_reason:
            errors["rejection_reason"] = "A rejection reason is required."
        if errors:
            raise ValidationError(errors)

    @property
    def is_overdue(self):
        return not self.completed_at and self.due_at < timezone.now()

    @property
    def days_remaining(self):
        return (self.due_at.date() - timezone.localdate()).days


class RequestTask(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        WORKING = "WORKING", "Working"
        DONE = "DONE", "Done"

    request = models.ForeignKey(PrivacyRequest, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=160)
    assignee = models.ForeignKey(User, on_delete=models.PROTECT, related_name="privacy_tasks")
    due_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        membership = getattr(self.assignee, "privacy_membership", None)
        if not membership or membership.organization_id != self.request.organization_id:
            raise ValidationError({"assignee": "Assignee must belong to this workspace."})

    def __str__(self):  # noqa: DJ012
        return f"{self.request.tracking_code} · {self.title}"

    @property
    def is_overdue(self):
        return self.status != self.Status.DONE and self.due_at < timezone.now()


class RequestEvent(models.Model):
    request = models.ForeignKey(PrivacyRequest, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    message = models.CharField(max_length=240)
    visible_to_subject = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.request.tracking_code} · {self.message[:40]}"
