from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Client, Invoice, LineItem, Membership, Organization, Payment


class BillingTests(TestCase):
    def setUp(self):
        self.a = Organization.objects.create(name="Alpha", slug="alpha")
        self.b = Organization.objects.create(name="Beta", slug="beta")
        self.ua = User.objects.create_user("alpha", password="StrongPass123!")
        self.ub = User.objects.create_user("beta", password="StrongPass123!")
        Membership.objects.create(user=self.ua, organization=self.a, role="owner")
        Membership.objects.create(user=self.ub, organization=self.b, role="owner")
        self.ca = Client.objects.create(organization=self.a, name="Alpha Client", email="a@example.com")
        self.cb = Client.objects.create(organization=self.b, name="Beta Client", email="b@example.com")
        self.ia = Invoice.objects.create(
            organization=self.a, client=self.ca, number="A-1", due_date=timezone.localdate() + timedelta(days=5)
        )
        self.ib = Invoice.objects.create(
            organization=self.b, client=self.cb, number="B-SECRET", due_date=timezone.localdate() + timedelta(days=5)
        )
        LineItem.objects.create(invoice=self.ia, description="Service", quantity=2, unit_price=Decimal("100"))
        LineItem.objects.create(invoice=self.ib, description="Secret", quantity=1, unit_price=Decimal("900"))
        self.client.force_login(self.ua)

    def test_dashboard_is_tenant_scoped(self):
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "A-1")
        self.assertNotContains(r, "B-SECRET")

    def test_invoice_list_is_tenant_scoped(self):
        r = self.client.get(reverse("invoices"))
        self.assertContains(r, "A-1")
        self.assertNotContains(r, "B-SECRET")

    def test_foreign_invoice_returns_404(self):
        self.assertEqual(self.client.get(reverse("invoice_detail", args=[self.ib.pk])).status_code, 404)

    def test_client_creation_assigns_tenant(self):
        self.client.post(reverse("clients"), {"name": "New", "email": "new@example.com"})
        self.assertTrue(Client.objects.filter(organization=self.a, email="new@example.com").exists())

    def test_invoice_form_rejects_foreign_client(self):
        r = self.client.post(
            reverse("create_invoice"),
            {"client": self.cb.pk, "number": "X", "issue_date": timezone.localdate(), "due_date": timezone.localdate(), "tax_rate": "18"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Invoice.objects.filter(number="X").exists())

    def test_add_item_to_foreign_invoice_blocked(self):
        self.assertEqual(
            self.client.post(
                reverse("add_item", args=[self.ib.pk]), {"description": "Hack", "quantity": "1", "unit_price": "1"}
            ).status_code,
            404,
        )

    def test_totals_and_tax(self):
        self.assertEqual(self.ia.subtotal, Decimal("200"))
        self.assertEqual(self.ia.tax_amount, Decimal("36.00"))
        self.assertEqual(self.ia.total, Decimal("236.00"))

    def test_partial_payment_updates_balance(self):
        Payment.objects.create(organization=self.a, invoice=self.ia, amount=Decimal("50"))
        self.assertEqual(self.ia.balance, Decimal("186.00"))

    def test_overpayment_is_rejected(self):
        self.client.post(reverse("add_payment", args=[self.ia.pk]), {"amount": "9999", "method": "Cash", "paid_on": timezone.localdate()})
        self.assertEqual(Payment.objects.count(), 0)

    def test_full_payment_marks_paid(self):
        self.client.post(reverse("add_payment", args=[self.ia.pk]), {"amount": "236", "method": "UPI", "paid_on": timezone.localdate()})
        self.ia.refresh_from_db()
        self.assertEqual(self.ia.status, "paid")

    def test_foreign_status_update_blocked(self):
        self.assertEqual(self.client.post(reverse("update_status", args=[self.ib.pk]), {"status": "void"}).status_code, 404)

    def test_api_is_tenant_scoped(self):
        p = self.client.get(reverse("api_invoices")).json()
        self.assertEqual(len(p["results"]), 1)
        self.assertEqual(p["results"][0]["number"], "A-1")

    def test_anonymous_api_redirects(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("api_clients")).status_code, 302)


class SignupTests(TestCase):
    def test_signup_creates_owner(self):
        r = self.client.post(
            reverse("signup"),
            {
                "username": "founder",
                "email": "f@example.com",
                "business_name": "Orbit Works",
                "password1": "VeryStrongPass123!",
                "password2": "VeryStrongPass123!",
            },
        )
        self.assertRedirects(r, reverse("dashboard"))
        self.assertEqual(User.objects.get(username="founder").billing_membership.role, "owner")

    def test_slug_collision(self):
        Organization.objects.create(name="Orbit Works", slug="orbit-works")
        self.client.post(
            reverse("signup"),
            {
                "username": "founder",
                "email": "f@example.com",
                "business_name": "Orbit Works",
                "password1": "VeryStrongPass123!",
                "password2": "VeryStrongPass123!",
            },
        )
        self.assertEqual(User.objects.get(username="founder").billing_membership.organization.slug, "orbit-works-2")
