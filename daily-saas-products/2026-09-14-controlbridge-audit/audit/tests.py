import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import RequestForm, SignupForm
from .models import AuditFinding, ControlArea, FindingEvent, Membership, Organization, RemediationTask
from .services import transition_finding, update_task


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ControlBridgeTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Alpha", slug="alpha")
        self.other = Organization.objects.create(name="Beta", slug="beta")
        self.owner = self.user("owner", Membership.Role.OWNER, self.org)
        self.manager = self.user("manager", Membership.Role.MANAGER, self.org)
        self.analyst = self.user("analyst", Membership.Role.ANALYST, self.org)
        self.viewer = self.user("viewer", Membership.Role.VIEWER, self.org)
        self.outsider = self.user("outsider", Membership.Role.OWNER, self.other)
        self.control_area = ControlArea.objects.create(organization=self.org, name="Sam", email="sam@example.com", department="India")
        self.item = AuditFinding.objects.create(
            organization=self.org,
            control_area=self.control_area,
            kind=AuditFinding.Kind.CONTROL_GAP,
            framework=AuditFinding.Framework.SOX,
            description="Send my information",
            due_at=timezone.now() + timedelta(days=20),
            assigned_to=self.analyst,
            created_by=self.owner,
        )

    def user(self, name, role, org):
        user = User.objects.create_user(name, password="StrongPass123!")
        Membership.objects.create(user=user, organization=org, role=role)
        return user

    def task(self, status=RemediationTask.Status.OPEN):
        return RemediationTask.objects.create(
            finding=self.item,
            title="Search CRM",
            assignee=self.analyst,
            due_at=timezone.now() + timedelta(days=2),
            status=status,
            completed_at=timezone.now() if status == RemediationTask.Status.DONE else None,
        )

    def test_role_capabilities(self):
        self.assertTrue(self.owner.audit_membership.can_manage)
        self.assertTrue(self.analyst.audit_membership.can_work)
        self.assertFalse(self.viewer.audit_membership.can_work)

    def test_tracking_code_is_generated(self):
        self.assertTrue(self.item.tracking_code.startswith("AUD-"))

    def test_overdue_and_days_remaining(self):
        self.item.due_at = timezone.now() - timedelta(days=2)
        self.assertTrue(self.item.is_overdue)
        self.assertLess(self.item.days_remaining, 0)

    def test_completed_finding_is_not_overdue(self):
        self.item.due_at = timezone.now() - timedelta(days=2)
        self.item.completed_at = timezone.now()
        self.assertFalse(self.item.is_overdue)

    def test_finding_rejects_cross_tenant_control_area(self):
        self.item.control_area = ControlArea.objects.create(organization=self.other, name="Other", email="other@example.com")
        with self.assertRaises(ValidationError):
            self.item.full_clean()

    def test_finding_rejects_cross_tenant_assignee(self):
        self.item.assigned_to = self.outsider
        with self.assertRaises(ValidationError):
            self.item.full_clean()

    def test_fulfilled_requires_evidence(self):
        self.item.status = AuditFinding.Status.RESOLVED
        with self.assertRaises(ValidationError):
            self.item.full_clean()

    def test_rejected_requires_reason(self):
        self.item.status = AuditFinding.Status.ACCEPTED_RISK
        with self.assertRaises(ValidationError):
            self.item.full_clean()

    def test_task_rejects_cross_tenant_assignee(self):
        task = self.task()
        task.assignee = self.outsider
        with self.assertRaises(ValidationError):
            task.full_clean()

    def test_workflow_happy_path(self):
        transition_finding(self.item.pk, self.analyst, AuditFinding.Status.TRIAGE)
        transition_finding(self.item.pk, self.analyst, AuditFinding.Status.REMEDIATION)
        self.task(RemediationTask.Status.DONE)
        transition_finding(self.item.pk, self.analyst, AuditFinding.Status.REVIEW)
        result = transition_finding(
            self.item.pk, self.manager, AuditFinding.Status.RESOLVED, "Export delivered securely.", "vault://demo-42"
        )
        self.assertEqual(result.status, AuditFinding.Status.RESOLVED)
        self.assertIsNotNone(result.completed_at)

    def test_illegal_transition_is_rejected(self):
        with self.assertRaises(ValidationError):
            transition_finding(self.item.pk, self.owner, AuditFinding.Status.RESOLVED, "Done", "ref")

    def test_cross_tenant_transition_is_forbidden(self):
        with self.assertRaises(PermissionDenied):
            transition_finding(self.item.pk, self.outsider, AuditFinding.Status.TRIAGE)

    def test_viewer_cannot_transition(self):
        with self.assertRaises(PermissionDenied):
            transition_finding(self.item.pk, self.viewer, AuditFinding.Status.TRIAGE)

    def test_analyst_cannot_reject(self):
        transition_finding(self.item.pk, self.analyst, AuditFinding.Status.TRIAGE)
        with self.assertRaises(PermissionDenied):
            transition_finding(self.item.pk, self.analyst, AuditFinding.Status.ACCEPTED_RISK, "Not valid")

    def test_review_requires_tasks(self):
        transition_finding(self.item.pk, self.analyst, AuditFinding.Status.TRIAGE)
        transition_finding(self.item.pk, self.analyst, AuditFinding.Status.REMEDIATION)
        with self.assertRaises(ValidationError):
            transition_finding(self.item.pk, self.analyst, AuditFinding.Status.REVIEW)

    def test_task_update_permissions_and_completion(self):
        task = self.task()
        updated = update_task(task, self.analyst, RemediationTask.Status.DONE, "Evidence attached")
        self.assertIsNotNone(updated.completed_at)
        with self.assertRaises(PermissionDenied):
            update_task(task, self.outsider, RemediationTask.Status.OPEN)

    def test_invalid_task_status(self):
        with self.assertRaises(ValidationError):
            update_task(self.task(), self.owner, "INVALID")

    def test_finding_form_scopes_relations(self):
        form = RequestForm(organization=self.org)
        self.assertNotIn(self.outsider, form.fields["assigned_to"].queryset)
        self.assertEqual(list(form.fields["control_area"].queryset), [self.control_area])

    def test_signup_creates_owner_and_unique_slug(self):
        form = SignupForm(
            {
                "username": "newuser",
                "email": "new@example.com",
                "organization_name": "Alpha",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.audit_membership.role, Membership.Role.OWNER)
        self.assertEqual(user.audit_membership.organization.slug, "alpha-2")

    def test_authentication_is_required(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_and_lists_render(self):
        self.client.force_login(self.owner)
        for name in ["dashboard", "finding_list", "control_area_list"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_landing_and_signup_pages_render(self):
        self.assertEqual(self.client.get(reverse("landing")).status_code, 200)
        self.assertEqual(self.client.get(reverse("signup")).status_code, 200)

    def test_finding_create_and_task_create_views(self):
        self.client.force_login(self.analyst)
        response = self.client.post(
            reverse("finding_create"),
            {
                "control_area": self.control_area.pk,
                "kind": AuditFinding.Kind.POLICY_BREACH,
                "framework": AuditFinding.Framework.SOX,
                "description": "Delete my profile and transaction metadata.",
                "due_at": (timezone.now() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M"),
                "assigned_to": self.analyst.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        created = AuditFinding.objects.exclude(pk=self.item.pk).get()
        self.assertRedirects(response, reverse("finding_detail", args=[created.pk]))
        response = self.client.post(
            reverse("task_create", args=[created.pk]),
            {
                "title": "Search billing platform",
                "assignee": self.analyst.pk,
                "due_at": (timezone.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
                "notes": "Export relevant records.",
            },
        )
        self.assertRedirects(response, reverse("finding_detail", args=[created.pk]))
        self.assertEqual(created.tasks.count(), 1)

    def test_tenant_detail_is_hidden(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("finding_detail", args=[self.item.pk])).status_code, 404)

    def test_viewer_cannot_create_finding(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("finding_create")).status_code, 403)

    def test_control_area_creation(self):
        self.client.force_login(self.analyst)
        response = self.client.post(reverse("control_area_list"), {"name": "Taylor", "email": "taylor@example.com", "department": "UK"})
        self.assertRedirects(response, reverse("control_area_list"))
        self.assertTrue(self.org.control_areas.filter(email="taylor@example.com").exists())

    def test_finding_search_and_status_filter(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("finding_list"), {"q": "sam"}), self.item.tracking_code)
        self.assertNotContains(self.client.get(reverse("finding_list"), {"status": AuditFinding.Status.RESOLVED}), self.item.tracking_code)

    def test_public_tracking_hides_personal_data_and_internal_events(self):
        FindingEvent.objects.create(
            finding=self.item, actor=self.owner, message="Internal email: sam@example.com", visible_to_stakeholders=False
        )
        response = self.client.get(reverse("public_tracking", args=[self.item.tracking_code]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "sam@example.com")

    def test_api_is_authenticated_and_tenant_scoped(self):
        self.assertEqual(self.client.get(reverse("api_findings")).status_code, 302)
        self.client.force_login(self.outsider)
        data = self.client.get(reverse("api_findings")).json()
        self.assertEqual(data["results"], [])

    def test_api_transition_and_invalid_json(self):
        self.client.force_login(self.analyst)
        url = reverse("api_transition", args=[self.item.pk])
        self.assertEqual(self.client.post(url, data="{", content_type="application/json").status_code, 400)
        response = self.client.post(url, data=json.dumps({"status": AuditFinding.Status.TRIAGE}), content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_seed_demo_is_idempotent(self):
        call_command("seed_demo")
        call_command("seed_demo")
        self.assertEqual(Organization.objects.filter(slug="northstar-digital").count(), 1)
        self.assertEqual(AuditFinding.objects.filter(organization__slug="northstar-digital").count(), 3)
