from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import AssetForm, WorkOrderForm, WorkOrderUpdateForm
from .models import Asset, Membership, Organization, Site, WorkLog, WorkOrder


class MaintainIQTests(TestCase):
    def setUp(self):
        self.alpha = Organization.objects.create(name="Alpha Facilities", slug="alpha")
        self.beta = Organization.objects.create(name="Beta Facilities", slug="beta")
        self.owner = User.objects.create_user("owner", password="ValidPass123!")
        self.tech = User.objects.create_user("tech", password="ValidPass123!")
        self.requester = User.objects.create_user("requester", password="ValidPass123!")
        self.outsider = User.objects.create_user("outsider", password="ValidPass123!")
        Membership.objects.create(user=self.owner, organization=self.alpha, role="owner")
        Membership.objects.create(user=self.tech, organization=self.alpha, role="technician")
        Membership.objects.create(user=self.requester, organization=self.alpha, role="requester")
        Membership.objects.create(user=self.outsider, organization=self.beta, role="owner")
        self.site = Site.objects.create(
            organization=self.alpha, name="Alpha HQ", address="One Main Street"
        )
        self.other_site = Site.objects.create(
            organization=self.alpha, name="Alpha Annex", address="Two Main Street"
        )
        self.foreign_site = Site.objects.create(
            organization=self.beta, name="Beta HQ", address="Foreign Street"
        )
        self.asset = Asset.objects.create(
            organization=self.alpha, site=self.site, tag="A-1", name="Air handler"
        )
        self.foreign_asset = Asset.objects.create(
            organization=self.beta, site=self.foreign_site, tag="B-1", name="Foreign asset"
        )
        self.order = WorkOrder.objects.create(
            organization=self.alpha,
            number="WO-A1",
            title="Repair airflow",
            description="Airflow is low",
            site=self.site,
            asset=self.asset,
            priority="high",
            due_at=timezone.now() - timedelta(hours=1),
            requested_by=self.requester,
        )
        self.owner_order = WorkOrder.objects.create(
            organization=self.alpha,
            number="WO-A2",
            title="Owner request",
            description="Owner-only request",
            site=self.site,
            requested_by=self.owner,
        )
        self.foreign_order = WorkOrder.objects.create(
            organization=self.beta,
            number="WO-B1",
            title="Foreign repair",
            description="Foreign tenant",
            site=self.foreign_site,
            asset=self.foreign_asset,
            requested_by=self.outsider,
        )
        self.client.force_login(self.owner)

    def test_manager_dashboard_is_tenant_scoped(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Repair airflow")
        self.assertNotContains(response, "Foreign repair")

    def test_requester_only_sees_own_orders(self):
        self.client.force_login(self.requester)
        response = self.client.get(reverse("work_orders"))
        self.assertContains(response, "Repair airflow")
        self.assertNotContains(response, "Owner request")

    def test_foreign_order_detail_is_not_found(self):
        response = self.client.get(reverse("work_order_detail", args=[self.foreign_order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_asset_form_hides_foreign_site(self):
        form = AssetForm(organization=self.alpha)
        self.assertIn(self.site, form.fields["site"].queryset)
        self.assertNotIn(self.foreign_site, form.fields["site"].queryset)

    def test_order_form_hides_foreign_assets(self):
        form = WorkOrderForm(organization=self.alpha)
        self.assertNotIn(self.foreign_asset, form.fields["asset"].queryset)

    def test_asset_must_belong_to_selected_site(self):
        form = WorkOrderForm(
            {
                "number": "WO-A3",
                "title": "Mismatch",
                "description": "Wrong location",
                "site": self.other_site.pk,
                "asset": self.asset.pk,
                "priority": "medium",
                "due_at": "",
            },
            organization=self.alpha,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("does not belong", form.errors["asset"][0])

    def test_work_order_created_inside_workspace(self):
        response = self.client.post(
            reverse("create_work_order"),
            {
                "number": "WO-A3",
                "title": "New repair",
                "description": "Fix this item",
                "site": self.site.pk,
                "asset": self.asset.pk,
                "priority": "medium",
                "due_at": "",
            },
        )
        created = WorkOrder.objects.get(number="WO-A3")
        self.assertRedirects(response, reverse("work_order_detail", args=[created.pk]))
        self.assertEqual(created.organization, self.alpha)
        self.assertEqual(created.requested_by, self.owner)

    def test_update_form_hides_requesters_and_outsiders(self):
        form = WorkOrderUpdateForm(instance=self.order, organization=self.alpha)
        self.assertIn(self.tech, form.fields["assigned_to"].queryset)
        self.assertNotIn(self.requester, form.fields["assigned_to"].queryset)
        self.assertNotIn(self.outsider, form.fields["assigned_to"].queryset)

    def test_owner_can_complete_work_order(self):
        self.client.post(
            reverse("work_order_detail", args=[self.order.pk]),
            {
                "action": "update",
                "update-status": "completed",
                "update-assigned_to": self.tech.pk,
                "update-due_at": "",
            },
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, WorkOrder.Status.COMPLETED)
        self.assertIsNotNone(self.order.completed_at)

    def test_requester_cannot_update_work_order(self):
        self.client.force_login(self.requester)
        self.client.post(
            reverse("work_order_detail", args=[self.order.pk]),
            {"action": "update", "update-status": "completed", "update-due_at": ""},
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, WorkOrder.Status.OPEN)

    def test_technician_can_add_service_log(self):
        self.client.force_login(self.tech)
        self.client.post(
            reverse("work_order_detail", args=[self.order.pk]),
            {"action": "log", "log-note": "Replaced filter", "log-hours": "1.5", "log-cost": "500"},
        )
        self.assertTrue(self.order.logs.filter(note="Replaced filter", author=self.tech).exists())

    def test_requester_cannot_add_service_log(self):
        self.client.force_login(self.requester)
        self.client.post(
            reverse("work_order_detail", args=[self.order.pk]),
            {"action": "log", "log-note": "Fake log", "log-hours": "1", "log-cost": "0"},
        )
        self.assertFalse(self.order.logs.filter(note="Fake log").exists())

    def test_owner_can_create_site(self):
        self.client.post(
            reverse("sites"),
            {"name": "New site", "address": "Address", "contact_name": "", "contact_phone": ""},
        )
        self.assertTrue(Site.objects.filter(organization=self.alpha, name="New site").exists())

    def test_requester_cannot_create_site(self):
        self.client.force_login(self.requester)
        self.client.post(
            reverse("sites"),
            {"name": "Forbidden", "address": "Address", "contact_name": "", "contact_phone": ""},
        )
        self.assertFalse(Site.objects.filter(name="Forbidden").exists())

    def test_overdue_property_ignores_completed_orders(self):
        self.assertTrue(self.order.is_overdue)
        self.order.status = WorkOrder.Status.COMPLETED
        self.assertFalse(self.order.is_overdue)

    def test_labor_cost_sums_logs(self):
        WorkLog.objects.create(
            organization=self.alpha,
            work_order=self.order,
            author=self.tech,
            note="First",
            cost="250.00",
        )
        WorkLog.objects.create(
            organization=self.alpha,
            work_order=self.order,
            author=self.tech,
            note="Second",
            cost="350.00",
        )
        self.assertEqual(self.order.labor_cost, Decimal("600.00"))

    def test_summary_api_is_tenant_scoped(self):
        data = self.client.get(reverse("api_summary")).json()
        self.assertEqual(data["workspace"], "Alpha Facilities")
        self.assertEqual(data["active"], 2)

    def test_requester_api_only_returns_own_orders(self):
        self.client.force_login(self.requester)
        rows = self.client.get(reverse("api_work_orders")).json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["number"], "WO-A1")

    def test_assets_api_is_tenant_scoped(self):
        rows = self.client.get(reverse("api_assets")).json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tag"], "A-1")

    def test_anonymous_user_redirects_to_login(self):
        self.client.logout()
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("login"))

    def test_signup_creates_owner_workspace(self):
        self.client.logout()
        response = self.client.post(
            reverse("signup"),
            {
                "username": "newowner",
                "email": "new@example.com",
                "business_name": "Bright Facilities",
                "password1": "FreshValidPass123!",
                "password2": "FreshValidPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        membership = User.objects.get(username="newowner").maintenance_membership
        self.assertEqual(membership.organization.slug, "bright-facilities")
        self.assertEqual(membership.role, Membership.Role.OWNER)
