from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify

from .models import (
    Membership,
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Supplier,
)


class SignupForm(UserCreationForm):
    email = forms.EmailField()
    business_name = forms.CharField(max_length=120)

    class Meta:
        model = User
        fields = ("username", "email", "business_name", "password1", "password2")

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            base = slugify(self.cleaned_data["business_name"]) or "warehouse"
            slug, suffix = base, 2
            while Organization.objects.filter(slug=slug).exists():
                slug, suffix = f"{base}-{suffix}", suffix + 1
            organization = Organization.objects.create(
                name=self.cleaned_data["business_name"], slug=slug
            )
            Membership.objects.create(
                user=user, organization=organization, role=Membership.Role.OWNER
            )
        return user


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ("name", "email", "phone", "lead_time_days")


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "sku",
            "name",
            "category",
            "supplier",
            "unit_cost",
            "sale_price",
            "reorder_level",
        )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(organization=organization)


class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ("product", "kind", "quantity", "reference", "note")
        help_texts = {
            "quantity": "Use a positive number for receipts and a negative number for issues."
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(
            organization=organization, active=True
        )

    def clean(self):
        data = super().clean()
        kind, quantity, product = data.get("kind"), data.get("quantity"), data.get("product")
        if kind == StockMovement.Kind.RECEIPT and quantity is not None and quantity < 1:
            self.add_error("quantity", "Receipts require a positive quantity.")
        if kind == StockMovement.Kind.ISSUE and quantity is not None and quantity > -1:
            self.add_error("quantity", "Issues require a negative quantity.")
        if product and quantity and product.quantity_on_hand + quantity < 0:
            self.add_error("quantity", "This movement would make stock negative.")
        return data


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ("number", "supplier", "expected_on", "notes")
        widgets = {"expected_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(organization=organization)


class PurchaseOrderItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ("product", "quantity", "unit_cost")

    def __init__(self, *args, organization=None, supplier=None, **kwargs):
        super().__init__(*args, **kwargs)
        products = Product.objects.filter(organization=organization, active=True)
        if supplier:
            products = products.filter(supplier=supplier)
        self.fields["product"].queryset = products
