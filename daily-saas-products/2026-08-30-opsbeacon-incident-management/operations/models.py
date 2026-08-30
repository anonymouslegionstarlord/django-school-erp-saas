from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    name = models.CharField(max_length=140)
    slug = models.SlugField(unique=True)
    status_page_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        COMMANDER = "commander", "Incident commander"
        RESPONDER = "responder", "Responder"
        VIEWER = "viewer", "Viewer"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="operations_membership"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.VIEWER)
    team = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f"{self.user.username} · {self.get_role_display()}"

    @property
    def can_manage(self):
        return self.role in [self.Role.OWNER, self.Role.COMMANDER]

    @property
    def can_respond(self):
        return self.role in [self.Role.OWNER, self.Role.COMMANDER, self.Role.RESPONDER]


class Service(models.Model):
    class Status(models.TextChoices):
        OPERATIONAL = "operational", "Operational"
        DEGRADED = "degraded", "Degraded performance"
        PARTIAL_OUTAGE = "partial_outage", "Partial outage"
        MAJOR_OUTAGE = "major_outage", "Major outage"
        MAINTENANCE = "maintenance", "Under maintenance"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="services"
    )
    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=140)
    description = models.TextField(max_length=1200, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPERATIONAL)
    owner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="owned_operations_services"
    )
    public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"], name="unique_operations_service_slug"
            )
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.organization_id and self.owner_id:
            membership = Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.owner_id
            ).first()
            if membership is None or not membership.can_respond:
                raise ValidationError(
                    {"owner": "Service owner must be a responder in this workspace."}
                )


class Incident(models.Model):
    class Severity(models.TextChoices):
        SEV1 = "sev1", "SEV-1 Critical"
        SEV2 = "sev2", "SEV-2 High"
        SEV3 = "sev3", "SEV-3 Medium"
        SEV4 = "sev4", "SEV-4 Low"

    class Status(models.TextChoices):
        INVESTIGATING = "investigating", "Investigating"
        IDENTIFIED = "identified", "Identified"
        MONITORING = "monitoring", "Monitoring"
        RESOLVED = "resolved", "Resolved"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="incidents"
    )
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="incidents")
    title = models.CharField(max_length=180)
    severity = models.CharField(max_length=4, choices=Severity.choices, default=Severity.SEV3)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.INVESTIGATING)
    summary = models.TextField(max_length=2500)
    customer_impact = models.TextField(max_length=1800, blank=True)
    resolution_summary = models.TextField(max_length=2500, blank=True)
    commander = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="commanded_incidents"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_operations_incidents"
    )
    started_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "severity", "-started_at"]

    def __str__(self):
        return f"{self.reference} · {self.title}"

    @property
    def reference(self):
        year = self.started_at.year if self.started_at else timezone.localdate().year
        return f"INC-{year}-{self.pk:04d}" if self.pk else f"INC-{year}-NEW"

    @property
    def is_active(self):
        return self.status != self.Status.RESOLVED

    @property
    def resolution_target_minutes(self):
        return {
            self.Severity.SEV1: 60,
            self.Severity.SEV2: 240,
            self.Severity.SEV3: 480,
            self.Severity.SEV4: 1440,
        }[self.severity]

    @property
    def duration_minutes(self):
        end = self.resolved_at or timezone.now()
        return max(0, round((end - self.started_at).total_seconds() / 60))

    @property
    def sla_breached(self):
        return self.duration_minutes > self.resolution_target_minutes

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.service_id
            and self.service.organization_id != self.organization_id
        ):
            errors["service"] = "Service must belong to this workspace."
        for field_name in ["commander", "created_by"]:
            user_id = getattr(self, f"{field_name}_id")
            if self.organization_id and user_id:
                membership = Membership.objects.filter(
                    organization_id=self.organization_id, user_id=user_id
                ).first()
                if membership is None:
                    errors[field_name] = "User must belong to this workspace."
                elif field_name == "commander" and not membership.can_respond:
                    errors[field_name] = "Commander must have response permissions."
        if self.status == self.Status.RESOLVED and not self.resolution_summary.strip():
            errors["resolution_summary"] = "A resolution summary is required."
        if self.resolved_at and self.resolved_at < self.started_at:
            errors["resolved_at"] = "Resolution cannot be earlier than incident start."
        if errors:
            raise ValidationError(errors)


class IncidentResponder(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="incident_responders"
    )
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="responders")
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="incident_response_assignments"
    )
    responsibility = models.CharField(max_length=140, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["incident", "user"], name="unique_operations_incident_responder"
            )
        ]

    def __str__(self):
        return f"{self.incident.reference} · {self.user.username}"

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.incident_id
            and self.incident.organization_id != self.organization_id
        ):
            errors["incident"] = "Incident must belong to this workspace."
        if self.organization_id and self.user_id:
            membership = Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.user_id
            ).first()
            if membership is None or not membership.can_respond:
                errors["user"] = "Responder must have response permissions in this workspace."
        if errors:
            raise ValidationError(errors)


class IncidentUpdate(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="incident_updates"
    )
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="updates")
    author = models.ForeignKey(User, on_delete=models.PROTECT, related_name="operations_updates")
    message = models.TextField(max_length=1800)
    status = models.CharField(max_length=14, choices=Incident.Status.choices)
    public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.incident.reference} · {self.get_status_display()}"

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.incident_id
            and self.incident.organization_id != self.organization_id
        ):
            errors["incident"] = "Incident must belong to this workspace."
        if (
            self.organization_id
            and self.author_id
            and not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.author_id
            ).exists()
        ):
            errors["author"] = "Author must belong to this workspace."
        if errors:
            raise ValidationError(errors)


class ActionItem(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        COMPLETED = "completed", "Completed"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="incident_actions"
    )
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="action_items")
    title = models.CharField(max_length=220)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="incident_action_items")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "due_date", "id"]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return bool(
            self.due_date
            and self.due_date < timezone.localdate()
            and self.status == self.Status.OPEN
        )

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.incident_id
            and self.incident.organization_id != self.organization_id
        ):
            errors["incident"] = "Incident must belong to this workspace."
        if (
            self.organization_id
            and self.owner_id
            and not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.owner_id
            ).exists()
        ):
            errors["owner"] = "Action owner must belong to this workspace."
        if errors:
            raise ValidationError(errors)
