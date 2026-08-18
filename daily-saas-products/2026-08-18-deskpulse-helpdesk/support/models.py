from datetime import timedelta

from django.contrib.auth.models import User
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
        AGENT = "agent", "Agent"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="support_membership")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.AGENT)


class Customer(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="customers")
    name = models.CharField(max_length=120)
    email = models.EmailField()
    company = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["organization", "email"], name="unique_customer_email_per_org")]

    def __str__(self):
        return self.name


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING = "waiting", "Waiting on customer"
        RESOLVED = "resolved", "Resolved"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="tickets")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="tickets")
    subject = models.CharField(max_length=180)
    description = models.TextField(max_length=4000)
    category = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.MEDIUM)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tickets")
    due_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def save(self, *args, **kwargs):
        if not self.due_at:
            hours = {self.Priority.URGENT: 2, self.Priority.HIGH: 8, self.Priority.MEDIUM: 24, self.Priority.LOW: 72}
            self.due_at = timezone.now() + timedelta(hours=hours[self.priority])
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        return self.status != self.Status.RESOLVED and self.due_at < timezone.now()

    def __str__(self):
        return f"#{self.pk} {self.subject}"


class Reply(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="replies")
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(User, on_delete=models.PROTECT)
    body = models.TextField(max_length=3000)
    internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
