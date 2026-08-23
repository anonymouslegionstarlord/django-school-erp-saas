from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import LeaveRequestForm
from .models import LeaveRequest, LeaveType, Membership, Organization


class LeaveLoomTests(TestCase):
    def setUp(self):
        self.alpha = Organization.objects.create(name="Alpha Team", slug="alpha")
        self.beta = Organization.objects.create(name="Beta Team", slug="beta")
        self.owner = User.objects.create_user("owner", password="ValidPass123!")
        self.employee = User.objects.create_user("employee", password="ValidPass123!")
        self.outsider = User.objects.create_user("outsider", password="ValidPass123!")
        Membership.objects.create(
            user=self.owner,
            organization=self.alpha,
            role=Membership.Role.OWNER,
            annual_allowance=24,
        )
        Membership.objects.create(
            user=self.employee,
            organization=self.alpha,
            role=Membership.Role.EMPLOYEE,
            annual_allowance=20,
        )
        Membership.objects.create(
            user=self.outsider, organization=self.beta, role=Membership.Role.OWNER
        )
        self.annual = LeaveType.objects.create(
            organization=self.alpha, name="Annual leave", color="#5965d8"
        )
        self.foreign_type = LeaveType.objects.create(
            organization=self.beta, name="Foreign leave", color="#d86767"
        )
        today = timezone.localdate()
        self.request = LeaveRequest.objects.create(
            organization=self.alpha,
            requester=self.employee,
            leave_type=self.annual,
            starts_on=today + timedelta(days=5),
            ends_on=today + timedelta(days=7),
            reason="Family event",
        )
        self.foreign_request = LeaveRequest.objects.create(
            organization=self.beta,
            requester=self.outsider,
            leave_type=self.foreign_type,
            starts_on=today + timedelta(days=5),
            ends_on=today + timedelta(days=6),
            reason="Foreign tenant",
        )
        self.client.force_login(self.owner)

    def test_dashboard_is_tenant_scoped(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Family event")
        self.assertNotContains(response, "Foreign tenant")

    def test_team_requests_are_tenant_scoped(self):
        response = self.client.get(reverse("requests"), {"scope": "team"})
        self.assertContains(response, "Family event")
        self.assertNotContains(response, "Foreign tenant")

    def test_employee_cannot_view_team_scope(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse("requests"), {"scope": "team"})
        self.assertEqual(response.context["scope"], "mine")

    def test_form_hides_foreign_leave_type(self):
        form = LeaveRequestForm(organization=self.alpha, requester=self.employee)
        self.assertIn(self.annual, form.fields["leave_type"].queryset)
        self.assertNotIn(self.foreign_type, form.fields["leave_type"].queryset)

    def test_end_before_start_is_rejected(self):
        form = LeaveRequestForm(
            {
                "leave_type": self.annual.pk,
                "starts_on": "2026-09-10",
                "ends_on": "2026-09-09",
                "reason": "Invalid range",
            },
            organization=self.alpha,
            requester=self.owner,
        )
        self.assertFalse(form.is_valid())

    def test_overlapping_request_is_rejected(self):
        form = LeaveRequestForm(
            {
                "leave_type": self.annual.pk,
                "starts_on": self.request.starts_on,
                "ends_on": self.request.ends_on,
                "reason": "Overlap",
            },
            organization=self.alpha,
            requester=self.employee,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("overlapping", form.non_field_errors()[0])

    def test_employee_can_create_request_in_workspace(self):
        self.client.force_login(self.employee)
        starts = self.request.ends_on + timedelta(days=5)
        response = self.client.post(
            reverse("create_request"),
            {
                "leave_type": self.annual.pk,
                "starts_on": starts,
                "ends_on": starts + timedelta(days=1),
                "reason": "New request",
            },
        )
        self.assertRedirects(response, reverse("requests"))
        self.assertTrue(
            LeaveRequest.objects.filter(
                organization=self.alpha, requester=self.employee, reason="New request"
            ).exists()
        )

    def test_owner_can_approve_employee_request(self):
        self.client.post(
            reverse("review_request", args=[self.request.pk]),
            {"decision": "approved", "review_note": "Enjoy"},
        )
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, LeaveRequest.Status.APPROVED)
        self.assertEqual(self.request.reviewed_by, self.owner)

    def test_employee_cannot_approve_request(self):
        self.client.force_login(self.employee)
        self.client.post(
            reverse("review_request", args=[self.request.pk]), {"decision": "approved"}
        )
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, LeaveRequest.Status.PENDING)

    def test_owner_cannot_self_approve(self):
        own = LeaveRequest.objects.create(
            organization=self.alpha,
            requester=self.owner,
            leave_type=self.annual,
            starts_on=self.request.ends_on + timedelta(days=10),
            ends_on=self.request.ends_on + timedelta(days=10),
            reason="Own request",
        )
        self.client.post(reverse("review_request", args=[own.pk]), {"decision": "approved"})
        own.refresh_from_db()
        self.assertEqual(own.status, LeaveRequest.Status.PENDING)

    def test_foreign_request_cannot_be_reviewed(self):
        response = self.client.post(
            reverse("review_request", args=[self.foreign_request.pk]),
            {"decision": "approved"},
        )
        self.assertEqual(response.status_code, 404)

    def test_employee_can_cancel_own_pending_request(self):
        self.client.force_login(self.employee)
        self.client.post(reverse("cancel_request", args=[self.request.pk]))
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, LeaveRequest.Status.CANCELLED)

    def test_employee_cannot_cancel_another_request(self):
        response = self.client.post(reverse("cancel_request", args=[self.request.pk]))
        self.assertEqual(response.status_code, 404)

    def test_business_days_excludes_weekend(self):
        item = LeaveRequest(
            organization=self.alpha,
            requester=self.employee,
            leave_type=self.annual,
            starts_on=date(2026, 8, 21),
            ends_on=date(2026, 8, 24),
            reason="Weekend",
        )
        self.assertEqual(item.business_days, 2)

    def test_summary_api_is_tenant_scoped(self):
        data = self.client.get(reverse("api_summary")).json()
        self.assertEqual(data["workspace"], "Alpha Team")
        self.assertEqual(data["pending_team_requests"], 1)

    def test_manager_api_can_see_team_requests(self):
        rows = self.client.get(reverse("api_requests")).json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["employee"], "employee")

    def test_employee_api_only_sees_own_requests(self):
        self.client.force_login(self.employee)
        rows = self.client.get(reverse("api_requests")).json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["employee"], "employee")

    def test_calendar_api_only_returns_approved_tenant_rows(self):
        self.request.status = LeaveRequest.Status.APPROVED
        self.request.save(update_fields=["status"])
        rows = self.client.get(reverse("api_calendar")).json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], self.request.pk)

    def test_anonymous_user_redirects_to_login(self):
        self.client.logout()
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("login"))

    def test_signup_creates_workspace_defaults(self):
        self.client.logout()
        response = self.client.post(
            reverse("signup"),
            {
                "username": "newowner",
                "email": "new@example.com",
                "company_name": "Bright Works",
                "password1": "FreshValidPass123!",
                "password2": "FreshValidPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        membership = User.objects.get(username="newowner").leave_membership
        self.assertEqual(membership.organization.slug, "bright-works")
        self.assertEqual(membership.organization.leave_types.count(), 2)
