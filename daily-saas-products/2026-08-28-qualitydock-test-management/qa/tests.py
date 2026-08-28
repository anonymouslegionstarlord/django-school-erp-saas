from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ExecutionUpdateForm, ProductForm, TestCaseForm, TestRunForm
from .models import (
    Activity,
    Membership,
    Organization,
    Product,
    TestExecution,
    TestRun,
    TestSuite,
)
from .models import (
    TestCase as QualityCase,
)


class QualityDockTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Alpha QA", slug="alpha-qa")
        self.other_org = Organization.objects.create(name="Private QA", slug="private-qa")
        self.owner = User.objects.create_user("owner", password="TestPass123!")
        self.lead = User.objects.create_user("lead", password="TestPass123!")
        self.tester = User.objects.create_user("tester", password="TestPass123!")
        self.viewer = User.objects.create_user("viewer", password="TestPass123!")
        self.foreign_user = User.objects.create_user("foreign", password="TestPass123!")
        for user, role in [
            (self.owner, Membership.Role.OWNER),
            (self.lead, Membership.Role.LEAD),
            (self.tester, Membership.Role.TESTER),
            (self.viewer, Membership.Role.VIEWER),
        ]:
            Membership.objects.create(user=user, organization=self.org, role=role)
        Membership.objects.create(
            user=self.foreign_user,
            organization=self.other_org,
            role=Membership.Role.OWNER,
        )
        self.product = Product.objects.create(
            organization=self.org,
            key="WEB",
            name="Web Store",
            description="Commerce experience",
            owner=self.lead,
        )
        self.foreign_product = Product.objects.create(
            organization=self.other_org,
            key="SEC",
            name="Secret Product",
            owner=self.foreign_user,
        )
        self.suite = TestSuite.objects.create(
            organization=self.org, product=self.product, name="Checkout"
        )
        self.foreign_suite = TestSuite.objects.create(
            organization=self.other_org,
            product=self.foreign_product,
            name="Private suite",
        )
        self.case = QualityCase.objects.create(
            organization=self.org,
            suite=self.suite,
            case_key="WEB-001",
            title="Guest checkout succeeds",
            requirement_reference="CHK-1",
            priority=QualityCase.Priority.CRITICAL,
            test_type=QualityCase.TestType.SMOKE,
            status=QualityCase.Status.READY,
            steps="1. Add item\n2. Checkout",
            expected_result="One paid order is created",
            created_by=self.lead,
        )
        self.second_case = QualityCase.objects.create(
            organization=self.org,
            suite=self.suite,
            case_key="WEB-002",
            title="Coupon applies",
            priority=QualityCase.Priority.HIGH,
            status=QualityCase.Status.READY,
            steps="Apply coupon",
            expected_result="Total is discounted",
            created_by=self.lead,
        )
        self.foreign_case = QualityCase.objects.create(
            organization=self.other_org,
            suite=self.foreign_suite,
            case_key="SEC-001",
            title="Private test",
            status=QualityCase.Status.READY,
            steps="Private",
            expected_result="Private",
            created_by=self.foreign_user,
        )
        self.run = TestRun.objects.create(
            organization=self.org,
            product=self.product,
            name="Release regression",
            target_version="1.2.0",
            environment=TestRun.Environment.STAGING,
            status=TestRun.Status.PLANNED,
            created_by=self.lead,
        )
        self.execution = TestExecution.objects.create(
            organization=self.org,
            run=self.run,
            test_case=self.case,
            assigned_to=self.tester,
        )
        self.unassigned = TestExecution.objects.create(
            organization=self.org,
            run=self.run,
            test_case=self.second_case,
        )
        self.foreign_run = TestRun.objects.create(
            organization=self.other_org,
            product=self.foreign_product,
            name="Private release",
            target_version="9.9",
            created_by=self.foreign_user,
        )

    def login(self, user=None):
        self.client.force_login(user or self.owner)

    def execution_payload(self, **overrides):
        payload = {
            "assigned_to": self.tester.pk,
            "status": TestExecution.Status.PASSED,
            "actual_result": "Observed expected behavior",
            "defect_reference": "",
            "evidence_url": "",
        }
        payload.update(overrides)
        return payload

    def test_anonymous_dashboard_redirects(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_dashboard_is_tenant_scoped(self):
        self.login()
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Web Store")
        self.assertNotContains(response, "Secret Product")

    def test_product_list_is_tenant_scoped(self):
        self.login()
        response = self.client.get(reverse("product_list"))
        self.assertContains(response, "Web Store")
        self.assertNotContains(response, "Secret Product")

    def test_case_list_is_tenant_scoped(self):
        self.login()
        response = self.client.get(reverse("case_list"))
        self.assertContains(response, "WEB-001")
        self.assertNotContains(response, "SEC-001")

    def test_run_list_is_tenant_scoped(self):
        self.login()
        response = self.client.get(reverse("run_list"))
        self.assertContains(response, "Release regression")
        self.assertNotContains(response, "Private release")

    def test_foreign_details_are_not_found(self):
        self.login()
        self.assertEqual(
            self.client.get(reverse("product_detail", args=[self.foreign_product.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("case_detail", args=[self.foreign_case.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("run_detail", args=[self.foreign_run.pk])).status_code,
            404,
        )

    def test_product_form_hides_foreign_users(self):
        form = ProductForm(organization=self.org)
        self.assertIn(self.lead, form.fields["owner"].queryset)
        self.assertNotIn(self.foreign_user, form.fields["owner"].queryset)
        self.assertNotIn(self.tester, form.fields["owner"].queryset)

    def test_case_form_hides_foreign_suites(self):
        form = TestCaseForm(organization=self.org)
        self.assertIn(self.suite, form.fields["suite"].queryset)
        self.assertNotIn(self.foreign_suite, form.fields["suite"].queryset)

    def test_run_form_hides_foreign_products(self):
        form = TestRunForm(organization=self.org)
        self.assertIn(self.product, form.fields["product"].queryset)
        self.assertNotIn(self.foreign_product, form.fields["product"].queryset)

    def test_execution_form_hides_foreign_assignee_and_viewer(self):
        form = ExecutionUpdateForm(instance=self.execution, organization=self.org)
        self.assertIn(self.tester, form.fields["assigned_to"].queryset)
        self.assertNotIn(self.foreign_user, form.fields["assigned_to"].queryset)
        self.assertNotIn(self.viewer, form.fields["assigned_to"].queryset)

    def test_lead_creates_product(self):
        self.login(self.lead)
        response = self.client.post(
            reverse("product_create"),
            {
                "key": "api",
                "name": "Public API",
                "description": "Partner endpoints",
                "owner": self.lead.pk,
                "status": Product.Status.ACTIVE,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Product.objects.filter(organization=self.org, key="API").exists())

    def test_duplicate_product_key_returns_form_error(self):
        self.login(self.owner)
        response = self.client.post(
            reverse("product_create"),
            {
                "key": "web",
                "name": "Duplicate",
                "description": "Duplicate",
                "owner": self.owner.pk,
                "status": Product.Status.ACTIVE,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_tester_cannot_create_product(self):
        self.login(self.tester)
        self.assertEqual(self.client.get(reverse("product_create")).status_code, 403)

    def test_lead_adds_suite_to_product(self):
        self.login(self.lead)
        response = self.client.post(
            reverse("suite_add", args=[self.product.pk]),
            {
                "product": self.product.pk,
                "name": "Orders",
                "description": "Order lifecycle",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TestSuite.objects.filter(organization=self.org, name="Orders").exists())

    def test_model_blocks_cross_tenant_suite_product(self):
        suite = TestSuite(organization=self.org, product=self.foreign_product, name="Invalid")
        with self.assertRaises(ValidationError):
            suite.full_clean()

    def test_lead_creates_test_case(self):
        self.login(self.lead)
        response = self.client.post(
            reverse("case_create"),
            {
                "suite": self.suite.pk,
                "case_key": "web-003",
                "title": "Payment succeeds",
                "requirement_reference": "PAY-3",
                "priority": QualityCase.Priority.HIGH,
                "test_type": QualityCase.TestType.FUNCTIONAL,
                "status": QualityCase.Status.READY,
                "preconditions": "Gateway online",
                "steps": "Pay for the order",
                "expected_result": "Payment is captured",
            },
        )
        self.assertEqual(response.status_code, 302)
        case = QualityCase.objects.get(case_key="WEB-003")
        self.assertEqual(case.organization, self.org)
        self.assertEqual(case.created_by, self.lead)

    def test_tester_cannot_author_case(self):
        self.login(self.tester)
        self.assertEqual(self.client.get(reverse("case_create")).status_code, 403)

    def test_owner_edits_test_case(self):
        self.login(self.owner)
        response = self.client.post(
            reverse("case_edit", args=[self.case.pk]),
            {
                "suite": self.suite.pk,
                "case_key": self.case.case_key,
                "title": "Guest checkout creates one order",
                "requirement_reference": "CHK-1",
                "priority": QualityCase.Priority.CRITICAL,
                "test_type": QualityCase.TestType.SMOKE,
                "status": QualityCase.Status.READY,
                "preconditions": "",
                "steps": "Checkout",
                "expected_result": "Exactly one order",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.case.refresh_from_db()
        self.assertIn("one order", self.case.title)

    def test_model_blocks_cross_tenant_case_suite(self):
        test_case = QualityCase(
            organization=self.org,
            suite=self.foreign_suite,
            case_key="BAD-1",
            title="Invalid",
            steps="Invalid",
            expected_result="Invalid",
            created_by=self.lead,
        )
        with self.assertRaises(ValidationError):
            test_case.full_clean()

    def test_lead_creates_run_with_ready_cases(self):
        self.login(self.lead)
        response = self.client.post(
            reverse("run_create"),
            {
                "product": self.product.pk,
                "name": "Hotfix verification",
                "target_version": "1.2.1",
                "environment": TestRun.Environment.QA,
                "start_date": timezone.localdate().isoformat(),
                "due_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
                "include_ready_cases": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        run = TestRun.objects.get(name="Hotfix verification")
        self.assertEqual(run.organization, self.org)
        self.assertEqual(run.executions.count(), 2)
        self.assertTrue(Activity.objects.filter(run=run).exists())

    def test_run_can_be_created_without_auto_scope(self):
        self.login(self.owner)
        self.client.post(
            reverse("run_create"),
            {
                "product": self.product.pk,
                "name": "Manual scope",
                "target_version": "2.0",
                "environment": TestRun.Environment.STAGING,
                "start_date": "",
                "due_date": "",
            },
        )
        self.assertEqual(TestRun.objects.get(name="Manual scope").executions.count(), 0)

    def test_tester_cannot_create_run(self):
        self.login(self.tester)
        self.assertEqual(self.client.get(reverse("run_create")).status_code, 403)

    def test_sync_ready_cases_does_not_duplicate_scope(self):
        self.login(self.lead)
        response = self.client.post(reverse("run_add_cases", args=[self.run.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.run.executions.count(), 2)

    def test_completed_run_cannot_accept_scope(self):
        self.run.status = TestRun.Status.COMPLETED
        self.run.save()
        self.login(self.owner)
        self.client.post(reverse("run_add_cases", args=[self.run.pk]))
        self.assertEqual(self.run.executions.count(), 2)

    def test_lead_starts_planned_run(self):
        self.login(self.lead)
        response = self.client.post(reverse("run_start", args=[self.run.pk]))
        self.assertEqual(response.status_code, 302)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, TestRun.Status.IN_PROGRESS)
        self.assertIsNotNone(self.run.start_date)

    def test_run_with_not_run_cases_cannot_complete(self):
        self.run.status = TestRun.Status.IN_PROGRESS
        self.run.save()
        self.login(self.owner)
        self.client.post(reverse("run_complete", args=[self.run.pk]))
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, TestRun.Status.IN_PROGRESS)

    def test_resolved_run_can_complete(self):
        self.run.status = TestRun.Status.IN_PROGRESS
        self.run.save()
        for execution in self.run.executions.all():
            execution.status = TestExecution.Status.PASSED
            execution.actual_result = "Passed"
            execution.save()
        self.login(self.lead)
        self.client.post(reverse("run_complete", args=[self.run.pk]))
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, TestRun.Status.COMPLETED)
        self.assertIsNotNone(self.run.completed_at)

    def test_assigned_tester_updates_execution(self):
        self.login(self.tester)
        response = self.client.post(
            reverse("execution_update", args=[self.run.pk, self.execution.pk]),
            self.execution_payload(),
        )
        self.assertEqual(response.status_code, 302)
        self.execution.refresh_from_db()
        self.run.refresh_from_db()
        self.assertEqual(self.execution.status, TestExecution.Status.PASSED)
        self.assertIsNotNone(self.execution.executed_at)
        self.assertEqual(self.run.status, TestRun.Status.IN_PROGRESS)

    def test_tester_cannot_update_unassigned_execution(self):
        self.login(self.tester)
        response = self.client.post(
            reverse("execution_update", args=[self.run.pk, self.unassigned.pk]),
            self.execution_payload(),
        )
        self.assertEqual(response.status_code, 403)

    def test_viewer_cannot_update_execution(self):
        self.login(self.viewer)
        response = self.client.post(
            reverse("execution_update", args=[self.run.pk, self.execution.pk]),
            self.execution_payload(),
        )
        self.assertEqual(response.status_code, 403)

    def test_failed_result_requires_defect_reference(self):
        self.login(self.lead)
        self.client.post(
            reverse("execution_update", args=[self.run.pk, self.execution.pk]),
            self.execution_payload(
                status=TestExecution.Status.FAILED,
                actual_result="Checkout total is wrong",
                defect_reference="",
            ),
        )
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, TestExecution.Status.NOT_RUN)

    def test_lead_records_failure_with_defect(self):
        self.login(self.lead)
        self.client.post(
            reverse("execution_update", args=[self.run.pk, self.execution.pk]),
            self.execution_payload(
                status=TestExecution.Status.FAILED,
                actual_result="Checkout total is wrong",
                defect_reference="https://example.com/QD-10",
            ),
        )
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, TestExecution.Status.FAILED)
        self.assertEqual(self.execution.defect_reference, "https://example.com/QD-10")

    def test_reset_to_not_run_clears_execution_timestamp(self):
        self.execution.status = TestExecution.Status.PASSED
        self.execution.save()
        self.assertIsNotNone(self.execution.executed_at)
        self.execution.status = TestExecution.Status.NOT_RUN
        self.execution.save()
        self.assertIsNone(self.execution.executed_at)

    def test_model_blocks_cross_tenant_execution(self):
        execution = TestExecution(
            organization=self.org,
            run=self.run,
            test_case=self.foreign_case,
            assigned_to=self.tester,
        )
        with self.assertRaises(ValidationError):
            execution.full_clean()

    def test_run_metrics_calculate_completion_and_pass_rate(self):
        self.execution.status = TestExecution.Status.PASSED
        self.execution.save()
        self.unassigned.status = TestExecution.Status.FAILED
        self.unassigned.actual_result = "Failed"
        self.unassigned.defect_reference = "BUG-1"
        self.unassigned.save()
        self.assertEqual(self.run.completion_rate, 100)
        self.assertEqual(self.run.pass_rate, 50)
        self.assertEqual(self.run.failed_count, 1)

    def test_tester_adds_run_comment(self):
        self.login(self.tester)
        response = self.client.post(
            reverse("run_comment", args=[self.run.pk]), {"message": "Build verified"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Activity.objects.filter(run=self.run, message="Build verified").exists())

    def test_viewer_cannot_add_run_comment(self):
        self.login(self.viewer)
        response = self.client.post(
            reverse("run_comment", args=[self.run.pk]), {"message": "No access"}
        )
        self.assertEqual(response.status_code, 403)

    def test_summary_api_is_tenant_scoped(self):
        self.login()
        payload = self.client.get(reverse("api_summary")).json()
        self.assertEqual(payload["workspace"], "Alpha QA")
        self.assertEqual(payload["products"], 1)
        self.assertEqual(payload["test_cases"], 2)

    def test_products_api_is_tenant_scoped(self):
        self.login()
        payload = self.client.get(reverse("api_products")).json()["results"]
        self.assertEqual([row["key"] for row in payload], ["WEB"])

    def test_cases_api_is_tenant_scoped(self):
        self.login()
        payload = self.client.get(reverse("api_cases")).json()["results"]
        self.assertEqual([row["key"] for row in payload], ["WEB-001", "WEB-002"])

    def test_runs_api_is_tenant_scoped(self):
        self.login()
        payload = self.client.get(reverse("api_runs")).json()["results"]
        self.assertEqual([row["name"] for row in payload], ["Release regression"])

    def test_run_detail_api_includes_only_workspace_executions(self):
        self.login()
        payload = self.client.get(reverse("api_run_detail", args=[self.run.pk])).json()
        self.assertEqual(payload["reference"], self.run.reference)
        self.assertEqual(len(payload["executions"]), 2)
        self.assertEqual(
            self.client.get(reverse("api_run_detail", args=[self.foreign_run.pk])).status_code,
            404,
        )

    def test_search_filters_case_library(self):
        self.login()
        response = self.client.get(reverse("case_list"), {"q": "coupon"})
        self.assertContains(response, "WEB-002")
        self.assertNotContains(response, "WEB-001")

    def test_signup_creates_owner_product_and_suite(self):
        response = self.client.post(
            reverse("signup"),
            {
                "organization_name": "Fresh QA",
                "username": "new_owner",
                "email": "owner@fresh.example",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        membership = User.objects.get(username="new_owner").quality_membership
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(membership.organization.products.count(), 1)
        self.assertEqual(membership.organization.test_suites.count(), 1)
