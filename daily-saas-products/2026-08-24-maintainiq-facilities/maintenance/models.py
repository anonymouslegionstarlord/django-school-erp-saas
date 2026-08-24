from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
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
        TECHNICIAN = "technician", "Technician"
        REQUESTER = "requester", "Requester"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="maintenance_membership"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.REQUESTER)

    @property
    def can_manage(self):
        return self.role in [self.Role.OWNER, self.Role.TECHNICIAN]


class Site(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="sites")
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=250)
    contact_name = models.CharField(max_length=120, blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_maintenance_site_per_org"
            )
        ]

    def __str__(self):
        return self.name


class Asset(models.Model):
    class Condition(models.TextChoices):
        GOOD = "good", "Good"
        WATCH = "watch", "Needs attention"
        DOWN = "down", "Out of service"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="assets")
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="assets")
    tag = models.CharField(max_length=40)
    name = models.CharField(max_length=140)
    category = models.CharField(max_length=80, blank=True)
    condition = models.CharField(max_length=10, choices=Condition.choices, default=Condition.GOOD)
    installed_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "tag"], name="unique_maintenance_asset_tag_per_org"
            )
        ]

    def __str__(self):
        return f"{self.tag} · {self.name}"


class WorkOrder(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In progress"
        ON_HOLD = "on_hold", "On hold"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="work_orders"
    )
    number = models.CharField(max_length=30)
    title = models.CharField(max_length=180)
    description = models.TextField(max_length=3000)
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="work_orders")
    asset = models.ForeignKey(
        Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_orders"
    )
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.OPEN)
    due_at = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="requested_work")
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_maintenance_work",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"], name="unique_work_order_number_per_org"
            )
        ]

    @property
    def is_overdue(self):
        return bool(
            self.due_at
            and self.due_at < timezone.now()
            and self.status not in [self.Status.COMPLETED, self.Status.CANCELLED]
        )

    @property
    def labor_cost(self):
        return sum((log.cost for log in self.logs.all()), Decimal("0"))

    def __str__(self):
        return f"{self.number} · {self.title}"


class WorkLog(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="work_logs"
    )
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="logs")
    author = models.ForeignKey(User, on_delete=models.PROTECT, related_name="maintenance_logs")
    note = models.TextField(max_length=1500)
    hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
