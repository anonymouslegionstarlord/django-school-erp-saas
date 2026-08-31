from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import AssessmentForm, FindingForm, FindingStatusForm, VendorForm
from .models import (
    Activity,
    Assessment,
    AssessmentControl,
    Finding,
    Membership,
    Organization,
    Vendor,
)
from .services import BASELINE_CONTROLS, create_baseline_controls


class VendorSentryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name="Atlas", slug="atlas")
        cls.other_organization = Organization.objects.create(name="Other", slug="other")
        cls.owner = cls._member("owner", Membership.Role.OWNER)
        cls.manager = cls._member("manager", Membership.Role.RISK_MANAGER)
        cls.analyst = cls._member("analyst", Membership.Role.ANALYST)
        cls.viewer = cls._member("viewer", Membership.Role.VIEWER)
        cls.other_owner = cls._member("other-owner", Membership.Role.OWNER, cls.other_organization)
        cls.unattached = User.objects.create_user("unattached", password="pass12345")
        cls.vendor = Vendor.objects.create(
            organization=cls.organization,
            name="Nimbus",
            slug="nimbus",
            category=Vendor.Category.CLOUD,
            criticality=Vendor.Criticality.CRITICAL,
            status=Vendor.Status.UNDER_REVIEW,
            service_description="Production hosting",
            business_owner=cls.owner,
            handles_personal_data=True,
            has_production_access=True,
            annual_spend=Decimal("120000.00"),
            next_review=timezone.localdate() - timedelta(days=1),
        )
        cls.other_vendor = Vendor.objects.create(
            organization=cls.other_organization,
            name="Other vendor",
            slug="other-vendor",
            category=Vendor.Category.OTHER,
            business_owner=cls.other_owner,
            service_description="Other tenant",
        )
        cls.assessment = Assessment.objects.create(
            organization=cls.organization,
            vendor=cls.vendor,
            title="Current review",
            scope="Security and privacy",
            assessor=cls.analyst,
            status=Assessment.Status.DRAFT,
            due_date=timezone.localdate() - timedelta(days=1),
        )
        create_baseline_controls(cls.assessment)
        first_control = cls.assessment.controls.first()
        first_control.response = AssessmentControl.Response.PARTIAL
        first_control.notes = "Partial implementation"
        first_control.save()
        cls.completed = Assessment.objects.create(
            organization=cls.organization,
            vendor=cls.vendor,
            title="Previous review",
            scope="Annual assurance",
            assessor=cls.manager,
            status=Assessment.Status.COMPLETED,
            due_date=timezone.localdate() - timedelta(days=50),
            completed_at=timezone.now() - timedelta(days=55),
        )
        completed_controls = create_baseline_controls(cls.completed)
        for control in completed_controls:
            control.response = AssessmentControl.Response.YES
            control.save()
        cls.finding = Finding.objects.create(
            organization=cls.organization,
            vendor=cls.vendor,
            assessment=cls.assessment,
            title="MFA gap",
            description="Privileged MFA is incomplete.",
            severity=Finding.Severity.HIGH,
            owner=cls.analyst,
            due_date=timezone.localdate() - timedelta(days=2),
        )
        cls.activity = Activity.objects.create(
            organization=cls.organization,
            actor=cls.manager,
            vendor=cls.vendor,
            assessment=cls.assessment,
            message="Review started.",
        )

    @classmethod
    def _member(cls, username, role, organization=None):
        user = User.objects.create_user(
            username,
            email=f"{username}@example.com",
            password="pass12345",
            first_name=username.title(),
        )
        Membership.objects.create(
            user=user,
            organization=organization or cls.organization,
            role=role,
            team="Risk",
        )
        return user

    def login(self, user=None):
        self.client.force_login(user or self.owner)

    def vendor_payload(self, **overrides):
        payload = {
            "name": "DataWorks",
            "slug": "dataworks",
            "category": Vendor.Category.DATA,
            "criticality": Vendor.Criticality.HIGH,
            "status": Vendor.Status.ACTIVE,
            "service_description": "Data analytics",
            "business_owner": self.owner.pk,
            "handles_personal_data": True,
            "annual_spend": "10000.00",
            "contract_expiry": timezone.localdate() + timedelta(days=90),
            "next_review": timezone.localdate() + timedelta(days=30),
        }
        payload.update(overrides)
        return payload

    def test_landing_and_login_redirect(self):
        response = self.client.get(reverse("landing"))
        self.assertContains(response, "Know which vendors deserve")
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_authenticated_landing_redirects(self):
        self.login()
        self.assertRedirects(self.client.get(reverse("landing")), reverse("dashboard"))

    def test_unattached_user_is_forbidden(self):
        self.login(self.unattached)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)

    def test_signup_creates_owner_and_starter_vendor(self):
        response = self.client.post(
            reverse("signup"),
            {
                "organization_name": "Acme Risk",
                "username": "acme-owner",
                "email": "acme@example.com",
                "password1": "LongerPass123!",
                "password2": "LongerPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="acme-owner")
        self.assertEqual(user.vendor_risk_membership.role, Membership.Role.OWNER)
        self.assertTrue(
            Vendor.objects.filter(
                organization=user.vendor_risk_membership.organization,
                slug="example-technology-vendor",
            ).exists()
        )

    def test_signup_makes_unique_slug(self):
        Organization.objects.create(name="Acme", slug="acme")
        self.client.post(
            reverse("signup"),
            {
                "organization_name": "Acme",
                "username": "second-acme",
                "email": "second@example.com",
                "password1": "LongerPass123!",
                "password2": "LongerPass123!",
            },
        )
        self.assertTrue(Organization.objects.filter(slug="acme-2").exists())

    def test_membership_permissions_and_labels(self):
        self.assertTrue(self.owner.vendor_risk_membership.can_manage)
        self.assertTrue(self.manager.vendor_risk_membership.can_manage)
        self.assertTrue(self.analyst.vendor_risk_membership.can_assess)
        self.assertFalse(self.analyst.vendor_risk_membership.can_manage)
        self.assertFalse(self.viewer.vendor_risk_membership.can_assess)
        self.assertEqual(str(self.organization), "Atlas")
        self.assertIn("Owner", str(self.owner.vendor_risk_membership))

    def test_vendor_properties_and_labels(self):
        self.assertEqual(str(self.vendor), "Nimbus")
        self.assertEqual(self.vendor.exposure_count, 2)
        self.assertTrue(self.vendor.is_review_due)
        self.assertEqual(self.vendor.risk_rating, "low")
        self.assertEqual(self.vendor.latest_assessment, self.completed)
        self.other_vendor.next_review = None
        self.assertFalse(self.other_vendor.is_review_due)
        self.assertEqual(self.other_vendor.risk_rating, "unassessed")

    def test_vendor_rejects_cross_tenant_owner(self):
        vendor = Vendor(
            organization=self.organization,
            name="Invalid",
            slug="invalid",
            category=Vendor.Category.OTHER,
            service_description="Invalid",
            business_owner=self.other_owner,
        )
        with self.assertRaises(ValidationError):
            vendor.full_clean()

    def test_assessment_progress_score_and_labels(self):
        self.assertIn("Current review", str(self.assessment))
        self.assertEqual(self.assessment.control_count, len(BASELINE_CONTROLS))
        self.assertEqual(self.assessment.answered_controls, 1)
        self.assertEqual(self.assessment.progress_percent, 12)
        self.assertEqual(self.assessment.score, 50)
        self.assertEqual(self.assessment.risk_rating, "high")
        self.assertTrue(self.assessment.is_overdue)
        self.assertEqual(self.completed.score, 0)
        self.assertEqual(self.completed.risk_rating, "low")
        self.assertFalse(self.completed.is_overdue)

    def test_assessment_risk_rating_thresholds(self):
        control = self.assessment.controls.first()
        expectations = [
            (AssessmentControl.Response.NO, "critical"),
            (AssessmentControl.Response.PARTIAL, "high"),
            (AssessmentControl.Response.YES, "low"),
            (AssessmentControl.Response.NOT_APPLICABLE, "unassessed"),
        ]
        for response, expected in expectations:
            self.assessment.controls.update(response=AssessmentControl.Response.UNANSWERED)
            control.response = response
            control.save()
            self.assertEqual(self.assessment.risk_rating, expected)

    def test_assessment_rejects_cross_tenant_vendor_and_assessor(self):
        assessment = Assessment(
            organization=self.organization,
            vendor=self.other_vendor,
            title="Invalid",
            scope="Invalid",
            assessor=self.other_owner,
            due_date=timezone.localdate(),
        )
        with self.assertRaises(ValidationError) as context:
            assessment.full_clean()
        self.assertIn("vendor", context.exception.message_dict)
        self.assertIn("assessor", context.exception.message_dict)

    def test_assessment_rejects_viewer_and_missing_completion_time(self):
        assessment = Assessment(
            organization=self.organization,
            vendor=self.vendor,
            title="Invalid",
            scope="Invalid",
            assessor=self.viewer,
            due_date=timezone.localdate(),
            status=Assessment.Status.COMPLETED,
        )
        with self.assertRaises(ValidationError) as context:
            assessment.full_clean()
        self.assertIn("assessor", context.exception.message_dict)
        self.assertIn("completed_at", context.exception.message_dict)

    def test_control_validation_and_risk_points(self):
        control = self.assessment.controls.first()
        self.assertIn("Security", str(control))
        control.response = AssessmentControl.Response.NO
        self.assertEqual(control.risk_points, control.weight * 20)
        control.response = AssessmentControl.Response.YES
        self.assertEqual(control.risk_points, 0)
        control.weight = 7
        with self.assertRaises(ValidationError):
            control.full_clean()
        control.weight = 3
        control.organization = self.other_organization
        with self.assertRaises(ValidationError):
            control.full_clean()

    def test_finding_validation_and_overdue(self):
        self.assertEqual(str(self.finding), "MFA gap")
        self.assertTrue(self.finding.is_overdue)
        self.finding.status = Finding.Status.ACCEPTED
        self.assertFalse(self.finding.is_overdue)
        self.finding.status = Finding.Status.RESOLVED
        self.finding.resolution_notes = ""
        self.finding.resolved_at = None
        with self.assertRaises(ValidationError) as context:
            self.finding.full_clean()
        self.assertIn("resolution_notes", context.exception.message_dict)
        self.assertIn("resolved_at", context.exception.message_dict)

    def test_finding_rejects_cross_tenant_relationships(self):
        finding = Finding(
            organization=self.organization,
            vendor=self.other_vendor,
            assessment=self.completed,
            title="Invalid",
            description="Invalid",
            severity=Finding.Severity.LOW,
            owner=self.other_owner,
        )
        with self.assertRaises(ValidationError) as context:
            finding.full_clean()
        self.assertIn("vendor", context.exception.message_dict)
        self.assertIn("assessment", context.exception.message_dict)
        self.assertIn("owner", context.exception.message_dict)

    def test_activity_validation_and_label(self):
        self.assertEqual(str(self.activity), "Review started.")
        other_assessment = Assessment.objects.create(
            organization=self.other_organization,
            vendor=self.other_vendor,
            title="Other assessment",
            scope="Other",
            assessor=self.other_owner,
            due_date=timezone.localdate(),
        )
        activity = Activity(
            organization=self.organization,
            actor=self.other_owner,
            vendor=self.other_vendor,
            assessment=other_assessment,
            message="Invalid",
        )
        with self.assertRaises(ValidationError) as context:
            activity.full_clean()
        self.assertIn("vendor", context.exception.message_dict)
        self.assertIn("actor", context.exception.message_dict)
        self.assertIn("assessment", context.exception.message_dict)

    def test_forms_scope_tenant_choices(self):
        vendor_form = VendorForm(organization=self.organization)
        self.assertIn(self.viewer, vendor_form.fields["business_owner"].queryset)
        self.assertNotIn(self.other_owner, vendor_form.fields["business_owner"].queryset)
        assessment_form = AssessmentForm(organization=self.organization)
        self.assertIn(self.vendor, assessment_form.fields["vendor"].queryset)
        self.assertNotIn(self.other_vendor, assessment_form.fields["vendor"].queryset)
        self.assertIn(self.analyst, assessment_form.fields["assessor"].queryset)
        self.assertNotIn(self.viewer, assessment_form.fields["assessor"].queryset)
        finding_form = FindingForm(organization=self.organization)
        self.assertIn(self.viewer, finding_form.fields["owner"].queryset)
        self.assertNotIn(self.other_owner, finding_form.fields["owner"].queryset)

    def test_vendor_form_slug_normalization_and_duplicate(self):
        form = VendorForm(self.vendor_payload(slug="Data-Works"), organization=self.organization)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["slug"], "data-works")
        form = VendorForm(self.vendor_payload(slug="Nimbus"), organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn("slug", form.errors)

    def test_finding_status_form_requires_resolution_notes(self):
        form = FindingStatusForm({"status": Finding.Status.RESOLVED})
        self.assertFalse(form.is_valid())
        self.assertIn("resolution_notes", form.errors)
        form = FindingStatusForm({"status": Finding.Status.RESOLVED, "resolution_notes": "Fixed."})
        self.assertTrue(form.is_valid())

    def test_baseline_control_creation_is_idempotent(self):
        create_baseline_controls(self.assessment)
        create_baseline_controls(self.assessment)
        self.assertEqual(self.assessment.controls.count(), len(BASELINE_CONTROLS))

    def test_dashboard_is_tenant_scoped(self):
        self.login()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nimbus")
        self.assertNotContains(response, "Other vendor")
        self.assertEqual(response.context["vendor_count"], 1)
        self.assertEqual(response.context["open_finding_count"], 1)
        self.assertEqual(response.context["average_score"], 0)

    def test_vendor_list_search_and_filters(self):
        self.login()
        response = self.client.get(
            reverse("vendor_list"),
            {
                "q": "production",
                "category": Vendor.Category.CLOUD,
                "criticality": Vendor.Criticality.CRITICAL,
                "status": Vendor.Status.UNDER_REVIEW,
            },
        )
        self.assertContains(response, "Nimbus")
        self.assertNotContains(response, "Other vendor")

    def test_viewer_cannot_create_or_edit_vendor(self):
        self.login(self.viewer)
        self.assertEqual(self.client.get(reverse("vendor_create")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("vendor_edit", args=[self.vendor.pk])).status_code,
            403,
        )

    def test_manager_creates_and_edits_vendor(self):
        self.login(self.manager)
        response = self.client.post(reverse("vendor_create"), self.vendor_payload())
        vendor = Vendor.objects.get(slug="dataworks")
        self.assertRedirects(response, reverse("vendor_detail", args=[vendor.pk]))
        self.assertTrue(vendor.activity.filter(message__contains="added").exists())
        response = self.client.post(
            reverse("vendor_edit", args=[vendor.pk]),
            self.vendor_payload(name="DataWorks Global"),
        )
        self.assertRedirects(response, reverse("vendor_detail", args=[vendor.pk]))
        vendor.refresh_from_db()
        self.assertEqual(vendor.name, "DataWorks Global")

    def test_vendor_detail_and_edit_cannot_cross_tenants(self):
        self.login()
        self.assertEqual(
            self.client.get(reverse("vendor_detail", args=[self.other_vendor.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("vendor_edit", args=[self.other_vendor.pk])).status_code,
            404,
        )

    def test_assessment_list_filters(self):
        self.login()
        response = self.client.get(
            reverse("assessment_list"),
            {"q": "current", "status": "draft", "vendor": self.vendor.pk},
        )
        self.assertContains(response, "Current review")
        self.assertNotContains(response, "Other vendor")

    def test_viewer_cannot_create_assessment(self):
        self.login(self.viewer)
        self.assertEqual(self.client.get(reverse("assessment_create")).status_code, 403)

    def test_analyst_creates_assessment_with_baseline(self):
        self.login(self.analyst)
        response = self.client.post(
            reverse("assessment_create"),
            {
                "vendor": self.vendor.pk,
                "title": "Renewal review",
                "scope": "Renewal assurance scope",
                "assessor": self.analyst.pk,
                "due_date": timezone.localdate() + timedelta(days=14),
            },
        )
        assessment = Assessment.objects.get(title="Renewal review")
        self.assertRedirects(response, reverse("assessment_detail", args=[assessment.pk]))
        self.assertEqual(assessment.controls.count(), len(BASELINE_CONTROLS))
        self.assertTrue(assessment.activity.filter(message__contains="started").exists())

    def test_assessment_create_query_vendor_is_tenant_scoped(self):
        self.login(self.analyst)
        response = self.client.get(reverse("assessment_create"), {"vendor": self.other_vendor.pk})
        self.assertEqual(response.status_code, 404)

    def test_assessment_detail_is_tenant_scoped_and_renders(self):
        self.login(self.analyst)
        response = self.client.get(reverse("assessment_detail", args=[self.assessment.pk]))
        self.assertContains(response, "Control responses")
        other = Assessment.objects.create(
            organization=self.other_organization,
            vendor=self.other_vendor,
            title="Other review",
            scope="Other",
            assessor=self.other_owner,
            due_date=timezone.localdate(),
        )
        self.assertEqual(
            self.client.get(reverse("assessment_detail", args=[other.pk])).status_code,
            404,
        )

    def test_assessor_updates_control_response(self):
        control = self.assessment.controls.last()
        self.login(self.analyst)
        response = self.client.post(
            reverse("control_update", args=[self.assessment.pk, control.pk]),
            {
                "response": AssessmentControl.Response.NO,
                "evidence": "https://example.com/evidence",
                "notes": "Gap confirmed",
            },
        )
        self.assertRedirects(response, reverse("assessment_detail", args=[self.assessment.pk]))
        control.refresh_from_db()
        self.assertEqual(control.response, AssessmentControl.Response.NO)

    def test_non_assessor_cannot_update_control(self):
        control = self.assessment.controls.last()
        self.login(self.viewer)
        response = self.client.post(
            reverse("control_update", args=[self.assessment.pk, control.pk]),
            {"response": AssessmentControl.Response.YES},
        )
        self.assertEqual(response.status_code, 403)

    def test_completed_assessment_controls_are_read_only(self):
        self.login(self.manager)
        response = self.client.post(
            reverse(
                "control_update",
                args=[self.completed.pk, self.completed.controls.first().pk],
            ),
            {"response": AssessmentControl.Response.NO},
        )
        self.assertEqual(response.status_code, 403)

    def test_assessor_moves_assessment_to_review(self):
        self.login(self.analyst)
        response = self.client.post(
            reverse("assessment_transition", args=[self.assessment.pk]),
            {"action": "review"},
        )
        self.assertRedirects(response, reverse("assessment_detail", args=[self.assessment.pk]))
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, Assessment.Status.IN_REVIEW)

    def test_assessment_completion_requires_every_control(self):
        self.login(self.analyst)
        response = self.client.post(
            reverse("assessment_transition", args=[self.assessment.pk]),
            {"action": "complete"},
        )
        self.assertRedirects(response, reverse("assessment_detail", args=[self.assessment.pk]))
        self.assessment.refresh_from_db()
        self.assertNotEqual(self.assessment.status, Assessment.Status.COMPLETED)

    def test_assessor_completes_assessment_and_schedules_review(self):
        self.assessment.controls.update(response=AssessmentControl.Response.YES)
        self.login(self.analyst)
        response = self.client.post(
            reverse("assessment_transition", args=[self.assessment.pk]),
            {"action": "complete"},
        )
        self.assertRedirects(response, reverse("assessment_detail", args=[self.assessment.pk]))
        self.assessment.refresh_from_db()
        self.vendor.refresh_from_db()
        self.assertEqual(self.assessment.status, Assessment.Status.COMPLETED)
        self.assertIsNotNone(self.assessment.completed_at)
        self.assertEqual(self.vendor.status, Vendor.Status.ACTIVE)
        self.assertEqual(self.vendor.next_review, timezone.localdate() + timedelta(days=365))

    def test_completed_and_unauthorized_transitions_are_forbidden(self):
        self.login(self.analyst)
        self.assertEqual(
            self.client.post(
                reverse("assessment_transition", args=[self.completed.pk]),
                {"action": "review"},
            ).status_code,
            403,
        )
        self.login(self.viewer)
        self.assertEqual(
            self.client.post(
                reverse("assessment_transition", args=[self.assessment.pk]),
                {"action": "review"},
            ).status_code,
            403,
        )

    def test_unknown_assessment_action_returns_bad_request(self):
        self.login(self.analyst)
        response = self.client.post(
            reverse("assessment_transition", args=[self.assessment.pk]),
            {"action": "unknown"},
        )
        self.assertEqual(response.status_code, 400)

    def test_analyst_adds_finding(self):
        self.login(self.analyst)
        response = self.client.post(
            reverse("finding_add", args=[self.assessment.pk]),
            {
                "title": "Logging gap",
                "description": "Admin events are retained for only seven days.",
                "severity": Finding.Severity.MEDIUM,
                "owner": self.viewer.pk,
                "due_date": timezone.localdate() + timedelta(days=20),
            },
        )
        self.assertRedirects(response, reverse("assessment_detail", args=[self.assessment.pk]))
        finding = Finding.objects.get(title="Logging gap")
        self.assertEqual(finding.vendor, self.vendor)
        self.assertTrue(self.vendor.activity.filter(message__contains="Logging gap").exists())

    def test_viewer_cannot_add_finding(self):
        self.login(self.viewer)
        response = self.client.post(
            reverse("finding_add", args=[self.assessment.pk]),
            {
                "title": "Forbidden",
                "description": "Forbidden",
                "severity": Finding.Severity.LOW,
                "owner": self.viewer.pk,
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_finding_owner_updates_and_resolves(self):
        self.login(self.analyst)
        response = self.client.post(
            reverse("finding_update", args=[self.finding.pk]),
            {"status": Finding.Status.IN_PROGRESS},
        )
        self.assertRedirects(response, reverse("assessment_detail", args=[self.assessment.pk]))
        response = self.client.post(
            reverse("finding_update", args=[self.finding.pk]),
            {
                "status": Finding.Status.RESOLVED,
                "resolution_notes": "MFA is enforced for every privileged workflow.",
            },
        )
        self.assertRedirects(response, reverse("assessment_detail", args=[self.assessment.pk]))
        self.finding.refresh_from_db()
        self.assertEqual(self.finding.status, Finding.Status.RESOLVED)
        self.assertIsNotNone(self.finding.resolved_at)

    def test_finding_resolution_without_notes_is_rejected(self):
        self.login(self.analyst)
        self.client.post(
            reverse("finding_update", args=[self.finding.pk]),
            {"status": Finding.Status.RESOLVED},
        )
        self.finding.refresh_from_db()
        self.assertEqual(self.finding.status, Finding.Status.OPEN)

    def test_unrelated_viewer_cannot_update_finding(self):
        self.login(self.viewer)
        response = self.client.post(
            reverse("finding_update", args=[self.finding.pk]),
            {"status": Finding.Status.ACCEPTED},
        )
        self.assertEqual(response.status_code, 403)

    def test_api_summary_requires_auth_and_is_scoped(self):
        self.assertEqual(self.client.get(reverse("api_summary")).status_code, 302)
        self.login(self.viewer)
        payload = self.client.get(reverse("api_summary")).json()
        self.assertEqual(payload["workspace"], "Atlas")
        self.assertEqual(payload["role"], Membership.Role.VIEWER)
        self.assertEqual(payload["vendors"], 1)
        self.assertEqual(payload["open_findings"], 1)

    def test_vendor_api_returns_risk_and_exposure(self):
        self.login()
        payload = self.client.get(reverse("api_vendors")).json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["name"], "Nimbus")
        self.assertEqual(payload["results"][0]["risk_rating"], "low")
        self.assertEqual(payload["results"][0]["exposure_count"], 2)

    def test_assessment_api_filters(self):
        self.login()
        payload = self.client.get(
            reverse("api_assessments"), {"status": Assessment.Status.DRAFT}
        ).json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["title"], "Current review")
        self.assertEqual(payload["results"][0]["progress_percent"], 12)

    def test_finding_api_filters(self):
        self.login()
        payload = self.client.get(
            reverse("api_findings"),
            {"status": Finding.Status.OPEN, "severity": Finding.Severity.HIGH},
        ).json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["title"], "MFA gap")
        self.assertTrue(payload["results"][0]["overdue"])

    def test_seed_demo_is_idempotent_and_accounts_authenticate(self):
        call_command("seed_demo", verbosity=0)
        counts = (
            Organization.objects.count(),
            Vendor.objects.count(),
            Assessment.objects.count(),
            AssessmentControl.objects.count(),
            Finding.objects.count(),
            Activity.objects.count(),
        )
        call_command("seed_demo", verbosity=0)
        self.assertEqual(
            counts,
            (
                Organization.objects.count(),
                Vendor.objects.count(),
                Assessment.objects.count(),
                AssessmentControl.objects.count(),
                Finding.objects.count(),
                Activity.objects.count(),
            ),
        )
        self.assertTrue(self.client.login(username="demo_risk", password="DemoPass123!"))
        self.assertContains(self.client.get(reverse("dashboard")), "NimbusCloud")
