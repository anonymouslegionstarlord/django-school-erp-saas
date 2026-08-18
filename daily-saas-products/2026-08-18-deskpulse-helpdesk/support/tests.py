from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Customer, Membership, Organization, Reply, Ticket


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name="Alpha Support", slug="alpha")
        self.org_b = Organization.objects.create(name="Beta Support", slug="beta")
        self.user_a = User.objects.create_user("alpha_agent", password="StrongPass123!")
        self.user_b = User.objects.create_user("beta_agent", password="StrongPass123!")
        Membership.objects.create(user=self.user_a, organization=self.org_a, role="owner")
        Membership.objects.create(user=self.user_b, organization=self.org_b, role="owner")
        self.customer_a = Customer.objects.create(organization=self.org_a, name="Alpha Customer", email="alpha@example.com")
        self.customer_b = Customer.objects.create(organization=self.org_b, name="Beta Customer", email="beta@example.com")
        self.ticket_a = Ticket.objects.create(
            organization=self.org_a, customer=self.customer_a, subject="Alpha Issue", description="Visible"
        )
        self.ticket_b = Ticket.objects.create(
            organization=self.org_b, customer=self.customer_b, subject="Secret Beta Issue", description="Hidden"
        )
        self.client.force_login(self.user_a)

    def test_dashboard_does_not_leak_other_workspace(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Alpha Issue")
        self.assertNotContains(response, "Secret Beta Issue")

    def test_ticket_list_is_tenant_scoped(self):
        response = self.client.get(reverse("tickets"))
        self.assertContains(response, "Alpha Issue")
        self.assertNotContains(response, "Secret Beta Issue")

    def test_foreign_ticket_detail_returns_404(self):
        self.assertEqual(self.client.get(reverse("ticket_detail", args=[self.ticket_b.pk])).status_code, 404)

    def test_customer_creation_assigns_workspace(self):
        self.client.post(reverse("customers"), {"name": "New Customer", "email": "new@example.com", "company": "NewCo"})
        self.assertTrue(Customer.objects.filter(organization=self.org_a, email="new@example.com").exists())
        self.assertFalse(Customer.objects.filter(organization=self.org_b, email="new@example.com").exists())

    def test_ticket_form_rejects_foreign_customer(self):
        response = self.client.post(
            reverse("create_ticket"), {"customer": self.customer_b.pk, "subject": "Intrusion", "description": "Attempt", "priority": "high"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Ticket.objects.filter(subject="Intrusion").exists())

    def test_reply_records_workspace_and_author(self):
        self.client.post(reverse("ticket_detail", args=[self.ticket_a.pk]), {"body": "We are investigating.", "internal": "on"})
        reply = Reply.objects.get(ticket=self.ticket_a)
        self.assertEqual(reply.organization, self.org_a)
        self.assertEqual(reply.author, self.user_a)
        self.assertTrue(reply.internal)

    def test_foreign_ticket_cannot_be_updated(self):
        response = self.client.post(reverse("update_ticket", args=[self.ticket_b.pk]), {"status": "resolved"})
        self.assertEqual(response.status_code, 404)
        self.ticket_b.refresh_from_db()
        self.assertEqual(self.ticket_b.status, Ticket.Status.OPEN)

    def test_ticket_filters(self):
        self.ticket_a.priority = Ticket.Priority.URGENT
        self.ticket_a.save()
        response = self.client.get(reverse("tickets"), {"priority": "urgent", "q": "Alpha"})
        self.assertContains(response, "Alpha Issue")

    def test_api_tickets_are_tenant_scoped(self):
        payload = self.client.get(reverse("api_tickets")).json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["subject"], "Alpha Issue")

    def test_api_summary_counts_only_current_workspace(self):
        payload = self.client.get(reverse("api_summary")).json()
        self.assertEqual(payload["active_tickets"], 1)
        self.assertEqual(payload["customers"], 1)

    def test_anonymous_api_request_redirects(self):
        self.client.logout()
        response = self.client.get(reverse("api_customers"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)


class WorkflowTests(TestCase):
    def test_signup_creates_owner_workspace(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "founder",
                "email": "founder@example.com",
                "organization_name": "Orbit Support",
                "password1": "VeryStrongPass123!",
                "password2": "VeryStrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        membership = User.objects.get(username="founder").support_membership
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(membership.organization.slug, "orbit-support")

    def test_slug_collision_gets_suffix(self):
        Organization.objects.create(name="Orbit Support", slug="orbit-support")
        self.client.post(
            reverse("signup"),
            {
                "username": "founder",
                "email": "founder@example.com",
                "organization_name": "Orbit Support",
                "password1": "VeryStrongPass123!",
                "password2": "VeryStrongPass123!",
            },
        )
        self.assertEqual(User.objects.get(username="founder").support_membership.organization.slug, "orbit-support-2")

    def test_sla_deadline_depends_on_priority(self):
        org = Organization.objects.create(name="SLA", slug="sla")
        customer = Customer.objects.create(organization=org, name="Customer", email="sla@example.com")
        before = timezone.now()
        ticket = Ticket.objects.create(organization=org, customer=customer, subject="Urgent", description="Help", priority="urgent")
        self.assertLess(ticket.due_at, before + timedelta(hours=3))

    def test_overdue_property_ignores_resolved_ticket(self):
        org = Organization.objects.create(name="SLA", slug="sla")
        customer = Customer.objects.create(organization=org, name="Customer", email="sla@example.com")
        ticket = Ticket.objects.create(
            organization=org,
            customer=customer,
            subject="Done",
            description="Help",
            status="resolved",
            due_at=timezone.now() - timedelta(hours=1),
        )
        self.assertFalse(ticket.is_overdue)
