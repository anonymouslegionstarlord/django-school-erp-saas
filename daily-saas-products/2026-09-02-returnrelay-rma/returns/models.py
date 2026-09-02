import calendar
from datetime import date
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
        CLAIMS_MANAGER = "claims_manager", "Claims manager"
        TECHNICIAN = "technician", "Technician"
        VIEWER = "viewer", "Viewer"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="returnrelay_membership"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=14, choices=Role.choices, default=Role.VIEWER)
    title = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f"{self.user.username} · {self.get_role_display()}"

    @property
    def can_manage(self):
        return self.role in [self.Role.OWNER, self.Role.CLAIMS_MANAGER]

    @property
    def can_inspect(self):
        return self.role in [
            self.Role.OWNER,
            self.Role.CLAIMS_MANAGER,
            self.Role.TECHNICIAN,
        ]


class Customer(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="customers"
    )
    name = models.CharField(max_length=160)
    contact_name = models.CharField(max_length=140)
    email = models.EmailField()
    phone = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_returnrelay_customer_name",
            )
        ]

    def __str__(self):
        return self.name


class Product(models.Model):
    class Category(models.TextChoices):
        ELECTRONICS = "electronics", "Electronics"
        APPLIANCE = "appliance", "Appliance"
        EQUIPMENT = "equipment", "Equipment"
        FURNITURE = "furniture", "Furniture"
        OTHER = "other", "Other"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="products"
    )
    sku = models.CharField(max_length=48)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=16, choices=Category.choices)
    retail_price = models.DecimalField(max_digits=11, decimal_places=2)
    warranty_months = models.PositiveSmallIntegerField(default=12)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "sku"], name="unique_returnrelay_product_sku"
            ),
            models.CheckConstraint(
                condition=models.Q(retail_price__gte=0),
                name="returnrelay_nonnegative_retail_price",
            ),
        ]

    def __str__(self):
        return f"{self.sku} · {self.name}"


class RegisteredItem(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="registered_items"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="items")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="items")
    serial_number = models.CharField(max_length=80)
    order_reference = models.CharField(max_length=80)
    purchase_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-purchase_date", "serial_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "serial_number"],
                name="unique_returnrelay_serial_number",
            )
        ]

    def __str__(self):
        return f"{self.product.name} · {self.serial_number}"

    @property
    def warranty_expires(self):
        month_index = (
            self.purchase_date.year * 12
            + self.purchase_date.month
            - 1
            + self.product.warranty_months
        )
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        day = min(self.purchase_date.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @property
    def is_in_warranty(self):
        return timezone.localdate() <= self.warranty_expires

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
            and self.customer_id
            and self.customer.organization_id != self.organization_id
        ):
            errors["customer"] = "Customer must belong to this workspace."
        if self.purchase_date and self.purchase_date > timezone.localdate():
            errors["purchase_date"] = "Purchase date cannot be in the future."
        if errors:
            raise ValidationError(errors)


class ReturnClaim(models.Model):
    class IssueCategory(models.TextChoices):
        DEFECTIVE = "defective", "Product defect"
        DAMAGED = "damaged", "Damaged in transit"
        WRONG_ITEM = "wrong_item", "Wrong item"
        PERFORMANCE = "performance", "Performance issue"
        OTHER = "other", "Other"

    class Remedy(models.TextChoices):
        REPAIR = "repair", "Repair"
        REPLACEMENT = "replacement", "Replacement"
        REFUND = "refund", "Refund"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        TRIAGE = "triage", "In triage"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        AWAITING_ITEM = "awaiting_item", "Awaiting item"
        RECEIVED = "received", "Item received"
        INSPECTING = "inspecting", "Inspecting"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Resolution(models.TextChoices):
        REPAIRED = "repaired", "Repaired"
        REPLACED = "replaced", "Replaced"
        REFUNDED = "refunded", "Refunded"
        STORE_CREDIT = "store_credit", "Store credit"
        NO_FAULT = "no_fault", "No fault found"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="claims")
    tracking_code = models.CharField(max_length=28)
    item = models.ForeignKey(RegisteredItem, on_delete=models.PROTECT, related_name="claims")
    issue_category = models.CharField(max_length=14, choices=IssueCategory.choices)
    description = models.TextField(max_length=2400)
    evidence_url = models.URLField(blank=True)
    requested_remedy = models.CharField(max_length=12, choices=Remedy.choices)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.SUBMITTED)
    response_due = models.DateTimeField()
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(max_length=1400, blank=True)
    resolution = models.CharField(max_length=14, choices=Resolution.choices, blank=True)
    resolution_summary = models.TextField(max_length=1800, blank=True)
    resolution_amount = models.DecimalField(
        max_digits=11, decimal_places=2, default=Decimal("0.00")
    )
    replacement_reference = models.CharField(max_length=100, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_returnrelay_claims"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["response_due", "-priority"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "tracking_code"],
                name="unique_returnrelay_claim_tracking",
            ),
            models.CheckConstraint(
                condition=models.Q(resolution_amount__gte=0),
                name="returnrelay_nonnegative_resolution_amount",
            ),
        ]

    def __str__(self):
        return f"{self.tracking_code} · {self.item.product.name}"

    @property
    def is_open(self):
        return self.status not in [self.Status.REJECTED, self.Status.CLOSED]

    @property
    def is_overdue(self):
        return (
            self.status
            not in [
                self.Status.REJECTED,
                self.Status.RESOLVED,
                self.Status.CLOSED,
            ]
            and self.response_due < timezone.now()
        )

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.item_id
            and self.item.organization_id != self.organization_id
        ):
            errors["item"] = "Registered item must belong to this workspace."
        if self.organization_id and self.created_by_id:
            if not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.created_by_id
            ).exists():
                errors["created_by"] = "Creator must belong to this workspace."
        if self.status == self.Status.REJECTED:
            if not self.rejected_at:
                errors["rejected_at"] = "Rejected claims require a timestamp."
            if not self.rejection_reason.strip():
                errors["rejection_reason"] = "A rejection reason is required."
        if self.status in [self.Status.RESOLVED, self.Status.CLOSED]:
            if not self.resolved_at:
                errors["resolved_at"] = "Resolved claims require a timestamp."
            if not self.resolution:
                errors["resolution"] = "Choose the final resolution."
            if not self.resolution_summary.strip():
                errors["resolution_summary"] = "A resolution summary is required."
            if (
                self.resolution
                in [
                    self.Resolution.REFUNDED,
                    self.Resolution.STORE_CREDIT,
                ]
                and self.resolution_amount <= 0
            ):
                errors["resolution_amount"] = "Refunds and credits require a positive amount."
            if (
                self.resolution == self.Resolution.REPLACED
                and not self.replacement_reference.strip()
            ):
                errors["replacement_reference"] = "Replacement reference is required."
        if self.status == self.Status.CLOSED and not self.closed_at:
            errors["closed_at"] = "Closed claims require a timestamp."
        if errors:
            raise ValidationError(errors)


class Inspection(models.Model):
    class Condition(models.TextChoices):
        LIKE_NEW = "like_new", "Like new"
        USED = "used", "Used"
        DAMAGED = "damaged", "Damaged"
        SEVERE = "severe", "Severely damaged"

    class Recommendation(models.TextChoices):
        REPAIR = "repair", "Repair"
        REPLACE = "replace", "Replace"
        REFUND = "refund", "Refund"
        DENY = "deny", "Deny claim"
        NO_FAULT = "no_fault", "No fault found"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="inspections"
    )
    claim = models.OneToOneField(ReturnClaim, on_delete=models.CASCADE, related_name="inspection")
    technician = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="returnrelay_inspections"
    )
    condition = models.CharField(max_length=10, choices=Condition.choices)
    fault_confirmed = models.BooleanField(default=False)
    findings = models.TextField(max_length=2200)
    recommendation = models.CharField(max_length=10, choices=Recommendation.choices)
    inspected_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-inspected_at"]

    def __str__(self):
        return f"Inspection · {self.claim.tracking_code}"

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.claim_id
            and self.claim.organization_id != self.organization_id
        ):
            errors["claim"] = "Claim must belong to this workspace."
        if self.organization_id and self.technician_id:
            membership = Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.technician_id
            ).first()
            if membership is None or not membership.can_inspect:
                errors["technician"] = "Technician needs inspection access in this workspace."
        if errors:
            raise ValidationError(errors)


class ClaimEvent(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="claim_events"
    )
    claim = models.ForeignKey(ReturnClaim, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="returnrelay_claim_events"
    )
    status = models.CharField(max_length=14, choices=ReturnClaim.Status.choices)
    message = models.CharField(max_length=600)
    visible_to_customer = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.claim.tracking_code} · {self.get_status_display()}"

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.claim_id
            and self.claim.organization_id != self.organization_id
        ):
            errors["claim"] = "Claim must belong to this workspace."
        if self.organization_id and self.actor_id:
            if not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.actor_id
            ).exists():
                errors["actor"] = "Actor must belong to this workspace."
        if errors:
            raise ValidationError(errors)
