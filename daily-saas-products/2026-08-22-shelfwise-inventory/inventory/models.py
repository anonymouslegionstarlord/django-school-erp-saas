from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum


class Organization(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Inventory manager"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="stock_membership")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.MANAGER)


class Supplier(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="suppliers"
    )
    name = models.CharField(max_length=140)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    lead_time_days = models.PositiveIntegerField(default=7)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"], name="unique_supplier_email_per_org"
            )
        ]

    def __str__(self):
        return self.name


class Product(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="products"
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    sku = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80, blank=True)
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    sale_price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    reorder_level = models.PositiveIntegerField(default=5)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "sku"], name="unique_product_sku_per_org"
            )
        ]

    @property
    def quantity_on_hand(self):
        return self.movements.aggregate(total=Sum("quantity"))["total"] or 0

    @property
    def stock_value(self):
        return Decimal(self.quantity_on_hand) * Decimal(str(self.unit_cost))

    @property
    def needs_reorder(self):
        return self.quantity_on_hand <= self.reorder_level

    def __str__(self):
        return f"{self.sku} · {self.name}"


class StockMovement(models.Model):
    class Kind(models.TextChoices):
        RECEIPT = "receipt", "Receipt"
        ISSUE = "issue", "Issue"
        ADJUSTMENT = "adjustment", "Adjustment"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="stock_movements"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="movements")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    quantity = models.IntegerField()
    reference = models.CharField(max_length=100, blank=True)
    note = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="stock_movements")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity=0), name="movement_quantity_nonzero"
            )
        ]


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ORDERED = "ordered", "Ordered"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="purchase_orders"
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    number = models.CharField(max_length=30)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    expected_on = models.DateField(null=True, blank=True)
    notes = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"], name="unique_purchase_order_number_per_org"
            )
        ]

    @property
    def total(self):
        return sum((item.line_total for item in self.items.all()), Decimal("0"))

    def __str__(self):
        return self.number


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order", "product"], name="unique_product_per_purchase_order"
            )
        ]

    @property
    def line_total(self):
        return Decimal(self.quantity) * self.unit_cost
