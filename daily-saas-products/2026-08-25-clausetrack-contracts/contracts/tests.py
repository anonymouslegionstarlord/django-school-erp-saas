from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ContractForm
from .models import Activity, Contract, Counterparty, Membership, Obligation, Organization


class ClauseTrackTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Alpha", slug="alpha")
        self.other_org = Organization.objects.create(name="Beta", slug="beta")
        self.owner = User.objects.create_user("owner", password="TestPass123!")
        self.viewer = User.objects.create_user("viewer", password="TestPass123!")
        self.foreign = User.objects.create_user("foreign", password="TestPass123!")
        Membership.objects.create(
            user=self.owner, organization=self.org, role=Membership.Role.OWNER
        )
        Membership.objects.create(
            user=self.viewer, organization=self.org, role=Membership.Role.VIEWER
        )
        Membership.objects.create(
            user=self.foreign, organization=self.other_org, role=Membership.Role.OWNER
        )
        self.party = Counterparty.objects.create(
            organization=self.org, name="Vendor", email="vendor@example.com"
        )
        self.foreign_party = Counterparty.objects.create(
            organization=self.other_org, name="Other", email="other@example.com"
        )
        today = timezone.localdate()
        self.contract = Contract.objects.create(
            organization=self.org,
            reference="A-1",
            title="Alpha contract",
            counterparty=self.party,
            owner=self.owner,
            starts_on=today,
            ends_on=today + timedelta(days=20),
            notice_days=30,
            status=Contract.Status.ACTIVE,
            value=100,
        )
        self.foreign_contract = Contract.objects.create(
            organization=self.other_org,
            reference="B-1",
            title="Secret contract",
            counterparty=self.foreign_party,
            owner=self.foreign,
            starts_on=today,
            ends_on=today + timedelta(days=100),
            status=Contract.Status.ACTIVE,
        )
        self.obligation = Obligation.objects.create(
            organization=self.org,
            contract=self.contract,
            title="File report",
            due_on=today - timedelta(days=1),
            assigned_to=self.owner,
        )
        self.foreign_obligation = Obligation.objects.create(
            organization=self.other_org,
            contract=self.foreign_contract,
            title="Foreign task",
            due_on=today,
            assigned_to=self.foreign,
        )

    def login(self, user=None):
        self.client.force_login(user or self.owner)

    def test_anonymous_dashboard_redirects(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_dashboard_is_tenant_scoped(self):
        self.login()
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Alpha contract")
        self.assertNotContains(response, "Secret contract")

    def test_contract_list_searches_and_isolates(self):
        self.login()
        response = self.client.get(reverse("contract_list"), {"q": "Alpha"})
        self.assertContains(response, "Alpha contract")
        self.assertNotContains(response, "Secret contract")

    def test_foreign_contract_detail_is_404(self):
        self.login()
        self.assertEqual(
            self.client.get(
                reverse("contract_detail", args=[self.foreign_contract.pk])
            ).status_code,
            404,
        )

    def test_owner_creates_contract_in_workspace(self):
        self.login()
        today = timezone.localdate()
        response = self.client.post(
            reverse("contract_create"),
            {
                "reference": "A-2",
                "title": "New deal",
                "kind": "vendor",
                "counterparty": self.party.pk,
                "owner": self.owner.pk,
                "value": "500",
                "starts_on": today,
                "ends_on": today + timedelta(days=100),
                "notice_days": 30,
                "status": "draft",
                "summary": "Useful terms",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Contract.objects.filter(organization=self.org, reference="A-2").exists())

    def test_contract_form_rejects_foreign_relations(self):
        form = ContractForm(organization=self.org)
        self.assertNotIn(self.foreign_party, form.fields["counterparty"].queryset)
        self.assertNotIn(self.foreign, form.fields["owner"].queryset)

    def test_contract_form_rejects_bad_dates(self):
        today = timezone.localdate()
        form = ContractForm(
            data={
                "reference": "BAD",
                "title": "Bad",
                "kind": "vendor",
                "counterparty": self.party.pk,
                "owner": self.owner.pk,
                "value": 0,
                "starts_on": today,
                "ends_on": today - timedelta(days=1),
                "notice_days": 30,
                "status": "draft",
            },
            organization=self.org,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("ends_on", form.errors)

    def test_viewer_cannot_create(self):
        self.login(self.viewer)
        self.assertRedirects(self.client.get(reverse("contract_create")), reverse("contract_list"))

    def test_viewer_cannot_update(self):
        self.login(self.viewer)
        response = self.client.post(
            reverse("contract_update", args=[self.contract.pk]),
            {"status": "terminated", "owner": self.owner.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_updates_status_and_records_activity(self):
        self.login()
        self.client.post(
            reverse("contract_update", args=[self.contract.pk]),
            {"status": "terminated", "owner": self.owner.pk},
        )
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, Contract.Status.TERMINATED)
        self.assertTrue(
            Activity.objects.filter(contract=self.contract, message__contains="Terminated").exists()
        )

    def test_owner_adds_obligation(self):
        self.login()
        self.client.post(
            reverse("obligation_add", args=[self.contract.pk]),
            {
                "title": "Review pricing",
                "due_on": timezone.localdate(),
                "assigned_to": self.viewer.pk,
            },
        )
        self.assertTrue(
            Obligation.objects.filter(organization=self.org, title="Review pricing").exists()
        )

    def test_complete_obligation(self):
        self.login()
        self.client.post(reverse("obligation_complete", args=[self.obligation.pk]))
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.status, Obligation.Status.COMPLETED)
        self.assertIsNotNone(self.obligation.completed_at)

    def test_foreign_obligation_cannot_be_completed(self):
        self.login()
        self.assertEqual(
            self.client.post(
                reverse("obligation_complete", args=[self.foreign_obligation.pk])
            ).status_code,
            404,
        )

    def test_counterparty_creation_and_viewer_denial(self):
        self.login()
        self.client.post(reverse("counterparties"), {"name": "New Co", "email": "new@example.com"})
        self.assertTrue(
            Counterparty.objects.filter(organization=self.org, email="new@example.com").exists()
        )
        self.login(self.viewer)
        self.assertEqual(
            self.client.post(
                reverse("counterparties"), {"name": "No", "email": "no@example.com"}
            ).status_code,
            403,
        )

    def test_api_contracts_is_tenant_scoped(self):
        self.login()
        payload = self.client.get(reverse("api_contracts")).json()
        self.assertEqual([row["reference"] for row in payload["results"]], ["A-1"])

    def test_api_obligations_is_tenant_scoped(self):
        self.login()
        payload = self.client.get(reverse("api_obligations")).json()
        self.assertEqual(len(payload["results"]), 1)

    def test_summary_api(self):
        self.login()
        self.assertEqual(self.client.get(reverse("api_summary")).json()["active_contracts"], 1)

    def test_contract_attention_and_overdue_logic(self):
        self.assertTrue(self.contract.needs_attention)
        self.assertEqual(self.contract.days_remaining, 20)
        self.assertTrue(self.obligation.is_overdue)
        self.assertEqual(self.contract.open_obligation_count, 1)

    def test_activity_note_is_tenant_scoped(self):
        self.login(self.viewer)
        self.client.post(
            reverse("activity_add", args=[self.contract.pk]), {"message": "Read and acknowledged"}
        )
        self.assertTrue(
            Activity.objects.filter(organization=self.org, message="Read and acknowledged").exists()
        )

    def test_signup_creates_owner_workspace(self):
        response = self.client.post(
            reverse("signup"),
            {
                "organization_name": "Fresh Legal",
                "username": "newowner",
                "email": "new@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(
            User.objects.get(username="newowner").contract_membership.role, Membership.Role.OWNER
        )
