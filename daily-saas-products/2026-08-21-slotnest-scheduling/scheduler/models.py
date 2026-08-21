from datetime import timedelta
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
        STAFF = "staff", "Staff"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="schedule_membership")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.STAFF)


class Service(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="services"
    )
    name = models.CharField(max_length=120)
    duration_minutes = models.PositiveIntegerField(default=60)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    color = models.CharField(max_length=7, default="#357A68")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_service_name_per_org"
            )
        ]

    def __str__(self):
        return self.name


class Customer(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="customers"
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    notes = models.TextField(max_length=500, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"], name="unique_booking_customer_email_per_org"
            )
        ]

    def __str__(self):
        return self.name


class Appointment(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CHECKED_IN = "checked_in", "Checked in"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No show"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="appointments"
    )
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="appointments")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="appointments")
    staff = models.ForeignKey(User, on_delete=models.PROTECT, related_name="appointments")
    starts_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CONFIRMED)
    notes = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "staff", "starts_at"], name="unique_staff_start_per_org"
            )
        ]

    @property
    def ends_at(self):
        return self.starts_at + timedelta(minutes=self.service.duration_minutes)

    @property
    def revenue(self):
        return self.service.price if self.status == self.Status.COMPLETED else Decimal("0")

    @property
    def is_past_due(self):
        return self.status == self.Status.CONFIRMED and self.starts_at < timezone.now()

    def __str__(self):
        return f"{self.customer} — {self.service}"
