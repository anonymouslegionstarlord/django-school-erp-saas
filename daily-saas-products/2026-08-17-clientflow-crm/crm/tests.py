from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Activity, Contact, Deal, Membership, Organization


class WorkspaceTestCase(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name="Alpha", slug="alpha")
        self.org_b = Organization.objects.create(name="Beta", slug="beta")
        self.user_a = User.objects.create_user("alpha_owner", password="StrongPass123!")
        self.user_b = User.objects.create_user("beta_owner", password="StrongPass123!")
        Membership.objects.create(user=self.user_a, organization=self.org_a, role="owner")
        Membership.objects.create(user=self.user_b, organization=self.org_b, role="owner")
        self.contact_a = Contact.objects.create(organization=self.org_a, name="Alpha Contact", email="alpha@example.com")
        self.contact_b = Contact.objects.create(organization=self.org_b, name="Beta Contact", email="beta@example.com")
        self.deal_a = Deal.objects.create(organization=self.org_a, contact=self.contact_a, title="Alpha Deal", value=Decimal("1000"))
        self.deal_b = Deal.objects.create(organization=self.org_b, contact=self.contact_b, title="Secret Beta Deal", value=Decimal("9000"))
        self.client.force_login(self.user_a)

    def test_dashboard_only_shows_workspace_deals(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Alpha Deal")
        self.assertNotContains(response, "Secret Beta Deal")

    def test_contacts_are_tenant_scoped(self):
        response = self.client.get(reverse("contacts"))
        self.assertContains(response, "Alpha Contact")
        self.assertNotContains(response, "Beta Contact")

    def test_contact_creation_assigns_current_workspace(self):
        self.client.post(reverse("contacts"), {"name": "New Lead", "email": "lead@example.com"})
        self.assertTrue(Contact.objects.filter(organization=self.org_a, email="lead@example.com").exists())
        self.assertFalse(Contact.objects.filter(organization=self.org_b, email="lead@example.com").exists())

    def test_deal_form_cannot_use_another_workspace_contact(self):
        response = self.client.post(reverse("deals"), {"contact": self.contact_b.pk, "title": "Intrusion", "value": "50", "stage": "lead"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Deal.objects.filter(title="Intrusion").exists())

    def test_stage_update_blocks_foreign_deal(self):
        response = self.client.post(reverse("update_stage", args=[self.deal_b.pk]), {"stage": "won"})
        self.assertEqual(response.status_code, 404)
        self.deal_b.refresh_from_db()
        self.assertEqual(self.deal_b.stage, "lead")

    def test_activity_creation_is_scoped_and_records_user(self):
        self.client.post(reverse("add_activity", args=[self.deal_a.pk]), {"kind": "call", "notes": "Discussed next steps"})
        activity = Activity.objects.get(deal=self.deal_a)
        self.assertEqual(activity.organization, self.org_a)
        self.assertEqual(activity.created_by, self.user_a)

    def test_foreign_activity_target_returns_404(self):
        response = self.client.post(reverse("add_activity", args=[self.deal_b.pk]), {"kind": "note", "notes": "No access"})
        self.assertEqual(response.status_code, 404)

    def test_summary_api_is_tenant_scoped(self):
        response = self.client.get(reverse("api_summary"))
        self.assertEqual(response.json()["deals"], 1)
        self.assertEqual(response.json()["pipeline_value"], "1000")

    def test_deals_api_does_not_leak_other_workspace(self):
        payload = self.client.get(reverse("api_deals")).json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["title"], "Alpha Deal")

    def test_anonymous_api_request_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("api_contacts"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)


class SignupTests(TestCase):
    def test_signup_creates_owner_and_unique_workspace(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "founder",
                "email": "founder@example.com",
                "organization_name": "Acme Sales",
                "password1": "VeryStrongPass123!",
                "password2": "VeryStrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        membership = User.objects.get(username="founder").membership
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(membership.organization.slug, "acme-sales")

    def test_workspace_slug_collision_is_handled(self):
        Organization.objects.create(name="Acme Sales", slug="acme-sales")
        self.client.post(
            reverse("signup"),
            {
                "username": "founder",
                "email": "founder@example.com",
                "organization_name": "Acme Sales",
                "password1": "VeryStrongPass123!",
                "password2": "VeryStrongPass123!",
            },
        )
        self.assertEqual(User.objects.get(username="founder").membership.organization.slug, "acme-sales-2")
