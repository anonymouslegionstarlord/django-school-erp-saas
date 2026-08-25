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
        LEGAL = "legal", "Legal manager"
        VIEWER = "viewer", "Viewer"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="contract_membership")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)

    @property
    def can_manage(self):
        return self.role in [self.Role.OWNER, self.Role.LEGAL]


class Counterparty(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="counterparties"
    )
    name = models.CharField(max_length=160)
    contact_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"], name="unique_contract_counterparty_email"
            )
        ]

    def __str__(self):
        return self.name


class Contract(models.Model):
    class Kind(models.TextChoices):
        VENDOR = "vendor", "Vendor agreement"
        CUSTOMER = "customer", "Customer agreement"
        NDA = "nda", "Non-disclosure agreement"
        LEASE = "lease", "Lease"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "In review"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        TERMINATED = "terminated", "Terminated"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="contracts"
    )
    reference = models.CharField(max_length=40)
    title = models.CharField(max_length=180)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.VENDOR)
    counterparty = models.ForeignKey(
        Counterparty, on_delete=models.PROTECT, related_name="contracts"
    )
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_contracts")
    value = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    starts_on = models.DateField()
    ends_on = models.DateField()
    notice_days = models.PositiveIntegerField(default=30)
    auto_renew = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    summary = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ends_on", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference"], name="unique_contract_reference_per_org"
            ),
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="contract_end_not_before_start",
            ),
        ]

    @property
    def days_remaining(self):
        return (self.ends_on - timezone.localdate()).days

    @property
    def needs_attention(self):
        return self.status == self.Status.ACTIVE and self.days_remaining <= self.notice_days

    @property
    def open_obligation_count(self):
        return self.obligations.filter(status=Obligation.Status.OPEN).count()

    def __str__(self):
        return f"{self.reference} · {self.title}"


class Obligation(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        COMPLETED = "completed", "Completed"
        WAIVED = "waived", "Waived"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="obligations"
    )
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="obligations")
    title = models.CharField(max_length=180)
    due_on = models.DateField()
    assigned_to = models.ForeignKey(User, on_delete=models.PROTECT, related_name="obligations")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_on", "title"]

    @property
    def is_overdue(self):
        return self.status == self.Status.OPEN and self.due_on < timezone.localdate()


class Activity(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="contract_activities"
    )
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="activities")
    author = models.ForeignKey(User, on_delete=models.PROTECT, related_name="contract_activities")
    message = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message
