from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        EMPLOYEE = "employee", "Employee"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="leave_membership")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.EMPLOYEE)
    job_title = models.CharField(max_length=100, blank=True)
    annual_allowance = models.PositiveIntegerField(default=20)

    @property
    def can_review(self):
        return self.role in [self.Role.OWNER, self.Role.MANAGER]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} · {self.get_role_display()}"


class LeaveType(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="leave_types"
    )
    name = models.CharField(max_length=80)
    color = models.CharField(max_length=7, default="#5965d8")
    paid = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_leave_type_per_org"
            )
        ]

    def __str__(self):
        return self.name


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="leave_requests"
    )
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="requests")
    starts_on = models.DateField()
    ends_on = models.DateField()
    reason = models.TextField(max_length=1000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_leave_requests",
    )
    review_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="leave_end_not_before_start",
            )
        ]

    @property
    def business_days(self):
        day, count = self.starts_on, 0
        while day <= self.ends_on:
            if day.weekday() < 5:
                count += 1
            day += timedelta(days=1)
        return count

    def __str__(self):
        return f"{self.requester} · {self.starts_on} to {self.ends_on}"
