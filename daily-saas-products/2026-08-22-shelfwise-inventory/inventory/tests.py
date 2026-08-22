from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ProductForm, StockMovementForm
from .models import (
    Membership,
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Supplier,
)


class ShelfWiseTests(TestCase):
    def setUp(self):
        self.alpha = Organization.objects.create(name="Alpha Store", slug="alpha")
        self.beta = Organization.objects.create(name="Beta Store", slug="beta")
        self.owner = User.objects.create_user("alpha_owner", password="ValidPass123!")
        self.outsider = User.objects.create_user("beta_owner", password="ValidPass123!")
        Membership.objects.create(user=self.owner, organization=self.alpha, role="owner")
        Membership.objects.create(user=self.outsider, organization=self.beta, role="owner")
        self.supplier = Supplier.objects.create(
            organization=self.alpha, name="Alpha Supply", email="alpha@supply.example"
        )
        self.foreign_supplier = Supplier.objects.create(
            organization=self.beta, name="Beta Supply", email="beta@supply.example"
        )
        self.product = Product.objects.create(
            organization=self.alpha,
            supplier=self.supplier,
            sku="A-1",
            name="Alpha product",
            unit_cost="10.00",
            sale_price="15.00",
            reorder_level=5,
        )
        self.foreign_product = Product.objects.create(
            organization=self.beta,
            supplier=self.foreign_supplier,
            sku="B-1",
            name="Beta product",
            unit_cost="20.00",
            sale_price="30.00",
        )
        StockMovement.objects.create(
            organization=self.alpha,
            product=self.product,
            kind="receipt",
            quantity=8,
            created_by=self.owner,
        )
        StockMovement.objects.create(
            organization=self.beta,
            product=self.foreign_product,
            kind="receipt",
            quantity=40,
            created_by=self.outsider,
        )
        self.order = PurchaseOrder.objects.create(
            organization=self.alpha,
            supplier=self.supplier,
            number="PO-A1",
            expected_on=timezone.localdate() + timedelta(days=5),
        )
        self.foreign_order = PurchaseOrder.objects.create(
            organization=self.beta, supplier=self.foreign_supplier, number="PO-B1"
        )
        self.client.force_login(self.owner)

    def test_dashboard_is_tenant_scoped(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Alpha product")
        self.assertNotContains(response, "Beta product")

    def test_product_catalog_is_tenant_scoped(self):
        response = self.client.get(reverse("products"))
        self.assertContains(response, "A-1")
        self.assertNotContains(response, "B-1")

    def test_product_form_hides_foreign_supplier(self):
        form = ProductForm(organization=self.alpha)
        self.assertIn(self.supplier, form.fields["supplier"].queryset)
        self.assertNotIn(self.foreign_supplier, form.fields["supplier"].queryset)

    def test_product_is_created_in_workspace(self):
        self.client.post(
            reverse("products"),
            {
                "sku": "A-2",
                "name": "New item",
                "category": "Tools",
                "supplier": self.supplier.pk,
                "unit_cost": "12.00",
                "sale_price": "19.00",
                "reorder_level": 3,
            },
        )
        self.assertTrue(Product.objects.filter(organization=self.alpha, sku="A-2").exists())

    def test_supplier_is_created_in_workspace(self):
        self.client.post(
            reverse("suppliers"),
            {
                "name": "Local Supply",
                "email": "local@example.com",
                "phone": "",
                "lead_time_days": 3,
            },
        )
        self.assertTrue(
            Supplier.objects.filter(organization=self.alpha, email="local@example.com").exists()
        )

    def test_movement_form_hides_foreign_product(self):
        form = StockMovementForm(organization=self.alpha)
        self.assertNotIn(self.foreign_product, form.fields["product"].queryset)

    def test_issue_cannot_make_stock_negative(self):
        form = StockMovementForm(
            {"product": self.product.pk, "kind": "issue", "quantity": -9},
            organization=self.alpha,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("make stock negative", form.errors["quantity"][0])

    def test_receipt_requires_positive_quantity(self):
        form = StockMovementForm(
            {"product": self.product.pk, "kind": "receipt", "quantity": -2},
            organization=self.alpha,
        )
        self.assertFalse(form.is_valid())

    def test_stock_calculations(self):
        self.assertEqual(self.product.quantity_on_hand, 8)
        self.assertEqual(self.product.stock_value, Decimal("80.00"))
        self.assertFalse(self.product.needs_reorder)

    def test_purchase_order_detail_blocks_foreign_tenant(self):
        response = self.client.get(reverse("purchase_order_detail", args=[self.foreign_order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_receiving_order_adds_stock_once(self):
        PurchaseOrderItem.objects.create(
            purchase_order=self.order, product=self.product, quantity=4, unit_cost="9.00"
        )
        url = reverse("receive_purchase_order", args=[self.order.pk])
        self.client.post(url)
        self.client.post(url)
        self.product.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.product.quantity_on_hand, 12)
        self.assertEqual(self.order.status, PurchaseOrder.Status.RECEIVED)

    def test_receiving_empty_order_does_not_change_status(self):
        self.client.post(reverse("receive_purchase_order", args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, PurchaseOrder.Status.DRAFT)

    def test_cancelled_order_cannot_be_received(self):
        self.order.status = PurchaseOrder.Status.CANCELLED
        self.order.save(update_fields=["status"])
        PurchaseOrderItem.objects.create(
            purchase_order=self.order, product=self.product, quantity=4, unit_cost="9.00"
        )
        self.client.post(reverse("receive_purchase_order", args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, PurchaseOrder.Status.CANCELLED)
        self.assertEqual(self.product.quantity_on_hand, 8)

    def test_summary_api_is_tenant_scoped(self):
        data = self.client.get(reverse("api_summary")).json()
        self.assertEqual(data["workspace"], "Alpha Store")
        self.assertEqual(data["units_on_hand"], 8)

    def test_products_api_is_tenant_scoped(self):
        rows = self.client.get(reverse("api_products")).json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sku"], "A-1")

    def test_movements_api_is_tenant_scoped(self):
        rows = self.client.get(reverse("api_movements")).json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sku"], "A-1")

    def test_anonymous_dashboard_redirects_to_login(self):
        self.client.logout()
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("login"))

    def test_signup_creates_owner_workspace(self):
        self.client.logout()
        response = self.client.post(
            reverse("signup"),
            {
                "username": "freshowner",
                "email": "fresh@example.com",
                "business_name": "Fresh Depot",
                "password1": "FreshValidPass123!",
                "password2": "FreshValidPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        membership = User.objects.get(username="freshowner").stock_membership
        self.assertEqual(membership.organization.slug, "fresh-depot")
        self.assertEqual(membership.role, Membership.Role.OWNER)
