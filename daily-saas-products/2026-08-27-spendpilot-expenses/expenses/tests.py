from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ExpenseItemForm, ExpenseReportForm
from .models import (
    Activity,
    CostCenter,
    ExpenseCategory,
    ExpenseItem,
    ExpenseReport,
    Membership,
    Organization,
)


class SpendPilotTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Alpha Studio", slug="alpha-studio", base_currency="INR"
        )
        self.other_org = Organization.objects.create(
            name="Private Company", slug="private-company", base_currency="USD"
        )
        self.owner = User.objects.create_user("owner", password="TestPass123!")
        self.manager = User.objects.create_user("manager", password="TestPass123!")
        self.employee = User.objects.create_user("employee", password="TestPass123!")
        self.finance = User.objects.create_user("finance", password="TestPass123!")
        self.other_employee = User.objects.create_user("other_employee", password="TestPass123!")
        self.foreign_user = User.objects.create_user("foreign", password="TestPass123!")
        for user, role in [
            (self.owner, Membership.Role.OWNER),
            (self.manager, Membership.Role.MANAGER),
            (self.employee, Membership.Role.EMPLOYEE),
            (self.finance, Membership.Role.FINANCE),
            (self.other_employee, Membership.Role.EMPLOYEE),
        ]:
            Membership.objects.create(user=user, organization=self.org, role=role)
        Membership.objects.create(
            user=self.foreign_user,
            organization=self.other_org,
            role=Membership.Role.OWNER,
        )
        self.cost_center = CostCenter.objects.create(
            organization=self.org, code="ENG", name="Engineering", manager=self.manager
        )
        self.foreign_cost_center = CostCenter.objects.create(
            organization=self.other_org,
            code="SECRET",
            name="Private",
            manager=self.foreign_user,
        )
        self.category = ExpenseCategory.objects.create(
            organization=self.org,
            name="Meals",
            daily_limit=Decimal("100.00"),
            receipt_required_over=Decimal("50.00"),
        )
        self.foreign_category = ExpenseCategory.objects.create(
            organization=self.other_org, name="Confidential"
        )
        self.report = ExpenseReport.objects.create(
            organization=self.org,
            submitter=self.employee,
            cost_center=self.cost_center,
            title="Customer workshop",
            purpose="Discovery workshop",
        )
        self.item = ExpenseItem.objects.create(
            organization=self.org,
            report=self.report,
            category=self.category,
            expense_date=timezone.localdate(),
            merchant="Cafe One",
            amount=Decimal("40.00"),
        )
        self.foreign_report = ExpenseReport.objects.create(
            organization=self.other_org,
            submitter=self.foreign_user,
            cost_center=self.foreign_cost_center,
            title="Confidential acquisition",
            purpose="Private",
        )

    def login(self, user=None):
        self.client.force_login(user or self.owner)

    def test_anonymous_dashboard_redirects_to_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_dashboard_is_tenant_scoped(self):
        self.login()
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Customer workshop")
        self.assertNotContains(response, "Confidential acquisition")

    def test_employee_only_sees_own_reports(self):
        ExpenseReport.objects.create(
            organization=self.org,
            submitter=self.other_employee,
            cost_center=self.cost_center,
            title="Another employee claim",
            purpose="Private to employee",
        )
        self.login(self.employee)
        response = self.client.get(reverse("report_list"))
        self.assertContains(response, "Customer workshop")
        self.assertNotContains(response, "Another employee claim")

    def test_manager_sees_workspace_reports_but_not_foreign_tenant(self):
        self.login(self.manager)
        response = self.client.get(reverse("report_list"))
        self.assertContains(response, "Customer workshop")
        self.assertNotContains(response, "Confidential acquisition")

    def test_foreign_report_detail_is_not_found(self):
        self.login()
        response = self.client.get(reverse("report_detail", args=[self.foreign_report.pk]))
        self.assertEqual(response.status_code, 404)

    def test_report_form_only_offers_workspace_cost_centers(self):
        form = ExpenseReportForm(organization=self.org)
        self.assertIn(self.cost_center, form.fields["cost_center"].queryset)
        self.assertNotIn(self.foreign_cost_center, form.fields["cost_center"].queryset)

    def test_item_form_only_offers_workspace_categories(self):
        form = ExpenseItemForm(organization=self.org)
        self.assertIn(self.category, form.fields["category"].queryset)
        self.assertNotIn(self.foreign_category, form.fields["category"].queryset)

    def test_employee_creates_report_in_own_workspace(self):
        self.login(self.employee)
        response = self.client.post(
            reverse("report_create"),
            {
                "title": "Conference travel",
                "cost_center": self.cost_center.pk,
                "purpose": "Attend DjangoCon",
                "trip_start": "",
                "trip_end": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        report = ExpenseReport.objects.get(title="Conference travel")
        self.assertEqual(report.organization, self.org)
        self.assertEqual(report.submitter, self.employee)
        self.assertTrue(Activity.objects.filter(report=report, action="created").exists())

    def test_submitter_adds_expense_and_records_activity(self):
        self.login(self.employee)
        response = self.client.post(
            reverse("item_add", args=[self.report.pk]),
            {
                "category": self.category.pk,
                "expense_date": timezone.localdate().isoformat(),
                "merchant": "Railway",
                "description": "Client train",
                "amount": "75.00",
                "receipt_url": "https://example.com/receipt",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.report.items.filter(merchant="Railway").exists())
        self.assertTrue(Activity.objects.filter(report=self.report, action="item_added").exists())

    def test_employee_cannot_add_to_another_users_report(self):
        report = ExpenseReport.objects.create(
            organization=self.org,
            submitter=self.other_employee,
            cost_center=self.cost_center,
            title="Other claim",
            purpose="Other",
        )
        self.login(self.employee)
        response = self.client.post(reverse("item_add", args=[report.pk]), {})
        self.assertEqual(response.status_code, 404)

    def test_submitter_can_remove_draft_item(self):
        self.login(self.employee)
        response = self.client.post(reverse("item_delete", args=[self.report.pk, self.item.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ExpenseItem.objects.filter(pk=self.item.pk).exists())

    def test_policy_flags_limit_and_missing_receipt(self):
        item = ExpenseItem.objects.create(
            organization=self.org,
            report=self.report,
            category=self.category,
            expense_date=timezone.localdate(),
            merchant="Large meal",
            amount=Decimal("125.00"),
        )
        self.assertIn("exceeds Meals daily limit", item.policy_note)
        self.assertIn("receipt required", item.policy_note)

    def test_policy_flags_date_outside_trip(self):
        self.report.trip_start = timezone.localdate() - timedelta(days=2)
        self.report.trip_end = timezone.localdate()
        self.report.save()
        item = ExpenseItem.objects.create(
            organization=self.org,
            report=self.report,
            category=self.category,
            expense_date=timezone.localdate() - timedelta(days=3),
            merchant="Early travel",
            amount=Decimal("20.00"),
        )
        self.assertIn("before trip", item.policy_note)

    def test_model_validation_blocks_cross_tenant_category(self):
        item = ExpenseItem(
            organization=self.org,
            report=self.report,
            category=self.foreign_category,
            expense_date=timezone.localdate(),
            merchant="Bad link",
            amount=Decimal("10.00"),
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_model_validation_blocks_cross_tenant_cost_center(self):
        report = ExpenseReport(
            organization=self.org,
            submitter=self.employee,
            cost_center=self.foreign_cost_center,
            title="Bad report",
            purpose="Cross tenant",
        )
        with self.assertRaises(ValidationError):
            report.full_clean()

    def test_report_total_and_policy_count(self):
        ExpenseItem.objects.create(
            organization=self.org,
            report=self.report,
            category=self.category,
            expense_date=timezone.localdate(),
            merchant="Large dinner",
            amount=Decimal("120.00"),
        )
        self.assertEqual(self.report.total_amount, Decimal("160.00"))
        self.assertEqual(self.report.policy_issue_count, 1)

    def test_report_cannot_submit_without_items(self):
        empty_report = ExpenseReport.objects.create(
            organization=self.org,
            submitter=self.employee,
            cost_center=self.cost_center,
            title="Empty report",
            purpose="Nothing yet",
        )
        self.login(self.employee)
        response = self.client.post(reverse("report_submit", args=[empty_report.pk]))
        self.assertEqual(response.status_code, 302)
        empty_report.refresh_from_db()
        self.assertEqual(empty_report.status, ExpenseReport.Status.DRAFT)

    def test_submitter_submits_report(self):
        self.login(self.employee)
        response = self.client.post(reverse("report_submit", args=[self.report.pk]))
        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ExpenseReport.Status.SUBMITTED)
        self.assertIsNotNone(self.report.submitted_at)

    def submit_report(self):
        self.report.status = ExpenseReport.Status.SUBMITTED
        self.report.submitted_at = timezone.now()
        self.report.save()

    def test_manager_approves_clean_report(self):
        self.submit_report()
        self.login(self.manager)
        response = self.client.post(
            reverse("report_decide", args=[self.report.pk]),
            {"action": "approve", "note": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ExpenseReport.Status.APPROVED)
        self.assertEqual(self.report.reviewed_by, self.manager)

    def test_flagged_approval_requires_exception_note(self):
        self.item.amount = Decimal("125.00")
        self.item.save()
        self.submit_report()
        self.login(self.manager)
        self.client.post(
            reverse("report_decide", args=[self.report.pk]),
            {"action": "approve", "note": ""},
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ExpenseReport.Status.SUBMITTED)

    def test_manager_can_approve_flag_with_note(self):
        self.item.amount = Decimal("125.00")
        self.item.save()
        self.submit_report()
        self.login(self.manager)
        self.client.post(
            reverse("report_decide", args=[self.report.pk]),
            {"action": "approve", "note": "Client dinner was pre-approved."},
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ExpenseReport.Status.APPROVED)

    def test_rejection_requires_reason(self):
        self.submit_report()
        self.login(self.manager)
        self.client.post(
            reverse("report_decide", args=[self.report.pk]),
            {"action": "reject", "note": ""},
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ExpenseReport.Status.SUBMITTED)

    def test_manager_rejects_and_submitter_can_resubmit(self):
        self.submit_report()
        self.login(self.manager)
        self.client.post(
            reverse("report_decide", args=[self.report.pk]),
            {"action": "reject", "note": "Add the client name."},
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ExpenseReport.Status.REJECTED)
        self.login(self.employee)
        self.client.post(reverse("report_submit", args=[self.report.pk]))
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ExpenseReport.Status.SUBMITTED)
        self.assertEqual(self.report.decision_note, "")

    def test_manager_cannot_self_approve(self):
        own_report = ExpenseReport.objects.create(
            organization=self.org,
            submitter=self.manager,
            cost_center=self.cost_center,
            title="Manager claim",
            purpose="Travel",
            status=ExpenseReport.Status.SUBMITTED,
        )
        self.login(self.manager)
        response = self.client.post(
            reverse("report_decide", args=[own_report.pk]),
            {"action": "approve", "note": ""},
        )
        self.assertEqual(response.status_code, 403)

    def test_employee_cannot_approve_report(self):
        self.submit_report()
        self.login(self.employee)
        response = self.client.post(
            reverse("report_decide", args=[self.report.pk]),
            {"action": "approve", "note": ""},
        )
        self.assertEqual(response.status_code, 403)

    def test_finance_marks_approved_report_reimbursed(self):
        self.report.status = ExpenseReport.Status.APPROVED
        self.report.save()
        self.login(self.finance)
        response = self.client.post(reverse("report_reimburse", args=[self.report.pk]))
        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ExpenseReport.Status.REIMBURSED)
        self.assertIsNotNone(self.report.reimbursed_at)

    def test_manager_cannot_record_reimbursement(self):
        self.report.status = ExpenseReport.Status.APPROVED
        self.report.save()
        self.login(self.manager)
        response = self.client.post(reverse("report_reimburse", args=[self.report.pk]))
        self.assertEqual(response.status_code, 403)

    def test_wrong_status_cannot_be_reimbursed(self):
        self.submit_report()
        self.login(self.owner)
        self.client.post(reverse("report_reimburse", args=[self.report.pk]))
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ExpenseReport.Status.SUBMITTED)

    def test_owner_adds_policy_category(self):
        self.login(self.owner)
        response = self.client.post(
            reverse("policy_settings"),
            {
                "kind": "category",
                "name": "Training",
                "daily_limit": "5000.00",
                "receipt_required_over": "100.00",
                "active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ExpenseCategory.objects.filter(organization=self.org, name="Training").exists()
        )

    def test_finance_adds_cost_center(self):
        self.login(self.finance)
        response = self.client.post(
            reverse("policy_settings"),
            {
                "kind": "cost_center",
                "code": "MKT",
                "name": "Marketing",
                "manager": self.manager.pk,
                "active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CostCenter.objects.filter(organization=self.org, code="MKT").exists())

    def test_duplicate_policy_values_return_form_errors(self):
        self.login(self.owner)
        response = self.client.post(
            reverse("policy_settings"),
            {
                "kind": "category",
                "name": "Meals",
                "daily_limit": "100.00",
                "receipt_required_over": "50.00",
                "active": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(
            ExpenseCategory.objects.filter(organization=self.org, name="Meals").count(), 1
        )

    def test_employee_cannot_open_policy_settings(self):
        self.login(self.employee)
        response = self.client.get(reverse("policy_settings"))
        self.assertEqual(response.status_code, 403)

    def test_comment_is_written_to_audit_trail(self):
        self.login(self.employee)
        response = self.client.post(
            reverse("comment_add", args=[self.report.pk]), {"message": "Receipt verified"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Activity.objects.filter(report=self.report, message="Receipt verified").exists()
        )

    def test_summary_api_is_role_and_tenant_scoped(self):
        ExpenseReport.objects.create(
            organization=self.org,
            submitter=self.other_employee,
            cost_center=self.cost_center,
            title="Other employee",
            purpose="Not visible",
        )
        self.login(self.employee)
        payload = self.client.get(reverse("api_summary")).json()
        self.assertEqual(payload["workspace"], "Alpha Studio")
        self.assertEqual(payload["role"], Membership.Role.EMPLOYEE)
        self.assertEqual(payload["reports"], 1)

    def test_reports_api_is_tenant_scoped_for_manager(self):
        self.login(self.manager)
        payload = self.client.get(reverse("api_reports")).json()["results"]
        self.assertEqual([row["title"] for row in payload], ["Customer workshop"])

    def test_api_report_detail_blocks_foreign_tenant(self):
        self.login(self.owner)
        response = self.client.get(reverse("api_report_detail", args=[self.foreign_report.pk]))
        self.assertEqual(response.status_code, 404)

    def test_policy_api_only_returns_workspace_configuration(self):
        self.login(self.owner)
        payload = self.client.get(reverse("api_policy")).json()
        self.assertEqual([row["name"] for row in payload["categories"]], ["Meals"])
        self.assertEqual([row["code"] for row in payload["cost_centers"]], ["ENG"])

    def test_report_search_supports_reference(self):
        self.login(self.owner)
        response = self.client.get(reverse("report_list"), {"q": self.report.reference})
        self.assertContains(response, "Customer workshop")
        self.assertNotContains(response, "Confidential acquisition")

    def test_signup_creates_owner_and_starter_policy(self):
        response = self.client.post(
            reverse("signup"),
            {
                "organization_name": "Fresh Company",
                "base_currency": "USD",
                "username": "new_owner",
                "email": "owner@fresh.example",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        membership = User.objects.get(username="new_owner").spend_membership
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(membership.organization.base_currency, "USD")
        self.assertEqual(membership.organization.expense_categories.count(), 3)
        self.assertEqual(membership.organization.cost_centers.count(), 1)
