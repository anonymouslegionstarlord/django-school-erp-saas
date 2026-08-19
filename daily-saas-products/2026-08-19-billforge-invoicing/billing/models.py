from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    tax_id = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ACCOUNTANT = "accountant", "Accountant"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="billing_membership")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.ACCOUNTANT)


class Client(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="clients")
    name = models.CharField(max_length=120)
    email = models.EmailField()
    company = models.CharField(max_length=120, blank=True)
    address = models.TextField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["organization", "email"], name="unique_client_email_per_org")]

    def __str__(self):
        return self.name


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invoices")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="invoices")
    number = models.CharField(max_length=30)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("18.00"), validators=[MinValueValidator(0)])
    notes = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        constraints = [models.UniqueConstraint(fields=["organization", "number"], name="unique_invoice_number_per_org")]

    @property
    def subtotal(self):
        return sum((item.amount for item in self.items.all()), Decimal("0"))

    @property
    def tax_amount(self):
        return (self.subtotal * self.tax_rate / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def total(self):
        return self.subtotal + self.tax_amount

    @property
    def paid_amount(self):
        return sum((payment.amount for payment in self.payments.all()), Decimal("0"))

    @property
    def balance(self):
        return max(self.total - self.paid_amount, Decimal("0"))

    @property
    def is_overdue(self):
        return self.status not in {self.Status.PAID, self.Status.VOID} and self.due_date < timezone.localdate() and self.balance > 0

    def __str__(self):
        return self.number


class LineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1, validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])

    @property
    def amount(self):
        return self.quantity * self.unit_price


class Payment(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="payments")
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    method = models.CharField(max_length=40, default="Bank transfer")
    reference = models.CharField(max_length=100, blank=True)
    paid_on = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-id"]
