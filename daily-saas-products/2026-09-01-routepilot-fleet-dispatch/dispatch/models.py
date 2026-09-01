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
        DISPATCHER = "dispatcher", "Dispatcher"
        DRIVER = "driver", "Driver"
        VIEWER = "viewer", "Viewer"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="routepilot_membership"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.VIEWER)
    title = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f"{self.user.username} · {self.get_role_display()}"

    @property
    def can_manage(self):
        return self.role in [self.Role.OWNER, self.Role.DISPATCHER]

    @property
    def can_dispatch(self):
        return self.can_manage


class Customer(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="customers"
    )
    name = models.CharField(max_length=160)
    contact_name = models.CharField(max_length=140)
    email = models.EmailField()
    phone = models.CharField(max_length=32)
    notes = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_routepilot_customer_name"
            )
        ]

    def __str__(self):
        return self.name


class DriverProfile(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        ON_ROUTE = "on_route", "On route"
        OFF_DUTY = "off_duty", "Off duty"
        SUSPENDED = "suspended", "Suspended"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="drivers")
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="routepilot_driver_profile"
    )
    license_number = models.CharField(max_length=64)
    license_expiry = models.DateField()
    phone = models.CharField(max_length=32)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AVAILABLE)

    class Meta:
        ordering = ["user__first_name", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "license_number"],
                name="unique_routepilot_driver_license",
            )
        ]

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    @property
    def is_license_valid(self):
        return self.license_expiry >= timezone.localdate()

    def clean(self):
        if self.organization_id and self.user_id:
            membership = Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.user_id
            ).first()
            if membership is None or membership.role != Membership.Role.DRIVER:
                raise ValidationError(
                    {"user": "Drivers must have the driver role in this workspace."}
                )


class Vehicle(models.Model):
    class Kind(models.TextChoices):
        BIKE = "bike", "Cargo bike"
        VAN = "van", "Delivery van"
        TRUCK = "truck", "Box truck"
        REFRIGERATED = "refrigerated", "Refrigerated truck"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        ON_ROUTE = "on_route", "On route"
        MAINTENANCE = "maintenance", "Maintenance"
        RETIRED = "retired", "Retired"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="vehicles"
    )
    registration = models.CharField(max_length=32)
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=14, choices=Kind.choices)
    capacity_kg = models.DecimalField(max_digits=9, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AVAILABLE)
    odometer_km = models.PositiveIntegerField(default=0)
    next_service_km = models.PositiveIntegerField(default=10_000)

    class Meta:
        ordering = ["registration"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "registration"],
                name="unique_routepilot_vehicle_registration",
            ),
            models.CheckConstraint(
                condition=models.Q(capacity_kg__gt=0),
                name="routepilot_vehicle_positive_capacity",
            ),
        ]

    def __str__(self):
        return f"{self.registration} · {self.name}"

    @property
    def is_service_due(self):
        return self.odometer_km >= self.next_service_km


class Shipment(models.Model):
    class Priority(models.TextChoices):
        STANDARD = "standard", "Standard"
        EXPRESS = "express", "Express"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        UNASSIGNED = "unassigned", "Unassigned"
        ASSIGNED = "assigned", "Assigned"
        PICKED_UP = "picked_up", "Picked up"
        IN_TRANSIT = "in_transit", "In transit"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Delivery failed"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="shipments"
    )
    tracking_code = models.CharField(max_length=24)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="shipments")
    pickup_address = models.TextField(max_length=600)
    delivery_address = models.TextField(max_length=600)
    package_description = models.CharField(max_length=240)
    weight_kg = models.DecimalField(max_digits=9, decimal_places=2)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.STANDARD)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.UNASSIGNED)
    scheduled_pickup = models.DateTimeField()
    delivery_deadline = models.DateTimeField()
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_reference = models.CharField(max_length=120, blank=True)
    proof_note = models.TextField(max_length=1000, blank=True)
    failure_reason = models.TextField(max_length=1000, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_routepilot_shipments"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["delivery_deadline", "-priority"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "tracking_code"],
                name="unique_routepilot_tracking_code",
            ),
            models.CheckConstraint(
                condition=models.Q(weight_kg__gt=Decimal("0")),
                name="routepilot_shipment_positive_weight",
            ),
        ]

    def __str__(self):
        return f"{self.tracking_code} · {self.customer.name}"

    @property
    def is_active(self):
        return self.status in [
            self.Status.ASSIGNED,
            self.Status.PICKED_UP,
            self.Status.IN_TRANSIT,
        ]

    @property
    def is_overdue(self):
        return self.status not in [self.Status.DELIVERED, self.Status.CANCELLED] and (
            self.delivery_deadline < timezone.now()
        )

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.customer_id
            and self.customer.organization_id != self.organization_id
        ):
            errors["customer"] = "Customer must belong to this workspace."
        if self.delivery_deadline and self.scheduled_pickup:
            if self.delivery_deadline <= self.scheduled_pickup:
                errors["delivery_deadline"] = "Deadline must be after the pickup time."
        if self.organization_id and self.created_by_id:
            if not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.created_by_id
            ).exists():
                errors["created_by"] = "Creator must belong to this workspace."
        if self.status == self.Status.DELIVERED:
            if not self.delivered_at:
                errors["delivered_at"] = "Delivered shipments require a timestamp."
            if not self.delivery_reference.strip():
                errors["delivery_reference"] = "A delivery reference is required."
            if not self.proof_note.strip():
                errors["proof_note"] = "A proof-of-delivery note is required."
        if self.status == self.Status.FAILED and not self.failure_reason.strip():
            errors["failure_reason"] = "A failure reason is required."
        if errors:
            raise ValidationError(errors)


class DispatchAssignment(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="assignments"
    )
    shipment = models.OneToOneField(Shipment, on_delete=models.CASCADE, related_name="assignment")
    driver = models.ForeignKey(DriverProfile, on_delete=models.PROTECT, related_name="assignments")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="assignments")
    assigned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="routepilot_assignments"
    )
    assigned_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.shipment.tracking_code} · {self.driver}"

    def clean(self):
        errors = {}
        if self.organization_id and self.shipment_id:
            if self.shipment.organization_id != self.organization_id:
                errors["shipment"] = "Shipment must belong to this workspace."
        if self.organization_id and self.driver_id:
            if self.driver.organization_id != self.organization_id:
                errors["driver"] = "Driver must belong to this workspace."
            elif not self.driver.is_license_valid:
                errors["driver"] = "Driver license is expired."
        if self.organization_id and self.vehicle_id:
            if self.vehicle.organization_id != self.organization_id:
                errors["vehicle"] = "Vehicle must belong to this workspace."
        if self.shipment_id and self.vehicle_id:
            if self.shipment.weight_kg > self.vehicle.capacity_kg:
                errors["vehicle"] = "Vehicle capacity is below the shipment weight."
        if self.organization_id and self.assigned_by_id:
            membership = Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.assigned_by_id
            ).first()
            if membership is None or not membership.can_dispatch:
                errors["assigned_by"] = "Only dispatchers can assign shipments."
        if errors:
            raise ValidationError(errors)


class ShipmentEvent(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="shipment_events"
    )
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="routepilot_shipment_events"
    )
    status = models.CharField(max_length=12, choices=Shipment.Status.choices)
    message = models.CharField(max_length=500)
    visible_to_customer = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.shipment.tracking_code} · {self.get_status_display()}"

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.shipment_id
            and self.shipment.organization_id != self.organization_id
        ):
            errors["shipment"] = "Shipment must belong to this workspace."
        if self.organization_id and self.actor_id:
            if not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.actor_id
            ).exists():
                errors["actor"] = "Actor must belong to this workspace."
        if errors:
            raise ValidationError(errors)
