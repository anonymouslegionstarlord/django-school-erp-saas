from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import (
    ActionItemForm,
    IncidentForm,
    IncidentUpdateForm,
    ResponderForm,
    ServiceForm,
)
from .models import (
    ActionItem,
    Incident,
    IncidentResponder,
    IncidentUpdate,
    Membership,
    Organization,
    Service,
)
from .views import recalculate_service_status


class OpsBeaconTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name="Northstar", slug="northstar")
        cls.other_organization = Organization.objects.create(name="Other Co", slug="other-co")
        cls.owner = cls._member("owner", Membership.Role.OWNER)
        cls.commander = cls._member("commander", Membership.Role.COMMANDER)
        cls.responder = cls._member("responder", Membership.Role.RESPONDER)
        cls.viewer = cls._member("viewer", Membership.Role.VIEWER)
        cls.other_owner = cls._member("other-owner", Membership.Role.OWNER, cls.other_organization)
        cls.unattached = User.objects.create_user("unattached", password="pass12345")
        cls.service = Service.objects.create(
            organization=cls.organization,
            name="API",
            slug="api",
            description="Customer API",
            owner=cls.owner,
        )
        cls.other_service = Service.objects.create(
            organization=cls.other_organization,
            name="Other API",
            slug="api",
            owner=cls.other_owner,
        )
        cls.incident = Incident.objects.create(
            organization=cls.organization,
            service=cls.service,
            title="Elevated errors",
            severity=Incident.Severity.SEV2,
            status=Incident.Status.INVESTIGATING,
            summary="Errors increased.",
            customer_impact="Some requests fail.",
            commander=cls.commander,
            created_by=cls.responder,
            started_at=timezone.now() - timedelta(minutes=30),
        )
        cls.initial_update = IncidentUpdate.objects.create(
            organization=cls.organization,
            incident=cls.incident,
            author=cls.commander,
            message="We are investigating.",
            status=Incident.Status.INVESTIGATING,
            public=True,
        )
        cls.internal_update = IncidentUpdate.objects.create(
            organization=cls.organization,
            incident=cls.incident,
            author=cls.responder,
            message="Internal trace identifier is abc-123.",
            status=Incident.Status.INVESTIGATING,
            public=False,
        )
        cls.assignment = IncidentResponder.objects.create(
            organization=cls.organization,
            incident=cls.incident,
            user=cls.commander,
            responsibility="Incident commander",
        )
        cls.action = ActionItem.objects.create(
            organization=cls.organization,
            incident=cls.incident,
            title="Write a runbook",
            owner=cls.responder,
            due_date=timezone.localdate() - timedelta(days=1),
        )
        cls.resolved = Incident.objects.create(
            organization=cls.organization,
            service=cls.service,
            title="Resolved failure",
            severity=Incident.Severity.SEV1,
            status=Incident.Status.RESOLVED,
            summary="Token failure.",
            resolution_summary="Rolled back the signing key.",
            commander=cls.owner,
            created_by=cls.owner,
            started_at=timezone.now() - timedelta(days=1, minutes=40),
            resolved_at=timezone.now() - timedelta(days=1),
        )
        IncidentUpdate.objects.create(
            organization=cls.organization,
            incident=cls.resolved,
            author=cls.owner,
            message="Service is restored.",
            status=Incident.Status.RESOLVED,
            public=True,
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
            team="Engineering",
        )
        return user

    def login(self, user=None):
        self.client.force_login(user or self.owner)

    def test_landing_and_login_redirect(self):
        response = self.client.get(reverse("landing"))
        self.assertContains(response, "Incident response without the chaos")
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_authenticated_landing_redirects_to_dashboard(self):
        self.login()
        self.assertRedirects(self.client.get(reverse("landing")), reverse("dashboard"))

    def test_unattached_account_is_forbidden(self):
        self.login(self.unattached)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_signup_creates_owner_workspace_and_starter_service(self):
        response = self.client.post(
            reverse("signup"),
            {
                "organization_name": "Acme Reliability",
                "username": "new-owner",
                "email": "new@example.com",
                "password1": "LongerPass123!",
                "password2": "LongerPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="new-owner")
        self.assertEqual(user.operations_membership.role, Membership.Role.OWNER)
        self.assertTrue(
            Service.objects.filter(
                organization=user.operations_membership.organization,
                slug="customer-platform",
            ).exists()
        )

    def test_signup_generates_unique_workspace_slug(self):
        Organization.objects.create(name="Acme", slug="acme")
        self.client.post(
            reverse("signup"),
            {
                "organization_name": "Acme",
                "username": "acme-owner",
                "email": "acme@example.com",
                "password1": "LongerPass123!",
                "password2": "LongerPass123!",
            },
        )
        self.assertTrue(Organization.objects.filter(slug="acme-2").exists())

    def test_membership_permissions(self):
        self.assertTrue(self.owner.operations_membership.can_manage)
        self.assertTrue(self.commander.operations_membership.can_manage)
        self.assertTrue(self.responder.operations_membership.can_respond)
        self.assertFalse(self.responder.operations_membership.can_manage)
        self.assertFalse(self.viewer.operations_membership.can_respond)

    def test_model_labels_and_incident_metrics(self):
        self.assertEqual(str(self.organization), "Northstar")
        self.assertEqual(str(self.service), "API")
        self.assertIn("owner", str(self.owner.operations_membership))
        self.assertIn("INC-", str(self.incident))
        self.assertIn("INC-", str(self.assignment))
        self.assertIn("Investigating", str(self.initial_update))
        self.assertEqual(str(self.action), "Write a runbook")
        self.assertTrue(self.incident.is_active)
        self.assertEqual(self.incident.resolution_target_minutes, 240)
        self.assertGreaterEqual(self.incident.duration_minutes, 29)
        self.assertFalse(self.incident.sla_breached)
        self.assertFalse(self.resolved.is_active)
        self.assertEqual(self.resolved.duration_minutes, 40)
        self.assertFalse(self.resolved.sla_breached)
        self.assertTrue(self.action.is_overdue)

    def test_all_severity_targets_and_breach(self):
        targets = {
            Incident.Severity.SEV1: 60,
            Incident.Severity.SEV2: 240,
            Incident.Severity.SEV3: 480,
            Incident.Severity.SEV4: 1440,
        }
        for severity, target in targets.items():
            self.incident.severity = severity
            self.assertEqual(self.incident.resolution_target_minutes, target)
        self.incident.severity = Incident.Severity.SEV1
        self.incident.started_at = timezone.now() - timedelta(minutes=61)
        self.assertTrue(self.incident.sla_breached)

    def test_service_rejects_cross_tenant_or_viewer_owner(self):
        for owner in [self.other_owner, self.viewer]:
            service = Service(
                organization=self.organization,
                name="Invalid",
                slug=f"invalid-{owner.pk}",
                owner=owner,
            )
            with self.assertRaises(ValidationError):
                service.full_clean()

    def test_incident_rejects_cross_tenant_relationships(self):
        incident = Incident(
            organization=self.organization,
            service=self.other_service,
            title="Invalid",
            summary="Invalid tenant.",
            commander=self.other_owner,
            created_by=self.other_owner,
        )
        with self.assertRaises(ValidationError) as context:
            incident.full_clean()
        self.assertIn("service", context.exception.message_dict)
        self.assertIn("commander", context.exception.message_dict)
        self.assertIn("created_by", context.exception.message_dict)

    def test_incident_requires_responder_commander(self):
        incident = Incident(
            organization=self.organization,
            service=self.service,
            title="Invalid commander",
            summary="Viewer cannot command.",
            commander=self.viewer,
            created_by=self.owner,
        )
        with self.assertRaises(ValidationError) as context:
            incident.full_clean()
        self.assertIn("commander", context.exception.message_dict)

    def test_incident_resolution_validation(self):
        self.incident.status = Incident.Status.RESOLVED
        self.incident.resolution_summary = ""
        self.incident.resolved_at = self.incident.started_at - timedelta(minutes=1)
        with self.assertRaises(ValidationError) as context:
            self.incident.full_clean()
        self.assertIn("resolution_summary", context.exception.message_dict)
        self.assertIn("resolved_at", context.exception.message_dict)

    def test_related_models_enforce_tenant_isolation(self):
        responder = IncidentResponder(
            organization=self.other_organization,
            incident=self.incident,
            user=self.viewer,
        )
        with self.assertRaises(ValidationError):
            responder.full_clean()
        update = IncidentUpdate(
            organization=self.other_organization,
            incident=self.incident,
            author=self.viewer,
            message="Wrong tenant",
            status=Incident.Status.INVESTIGATING,
        )
        with self.assertRaises(ValidationError):
            update.full_clean()
        action = ActionItem(
            organization=self.other_organization,
            incident=self.incident,
            title="Wrong tenant",
            owner=self.viewer,
        )
        with self.assertRaises(ValidationError):
            action.full_clean()

    def test_forms_scope_tenant_choices(self):
        service_form = ServiceForm(organization=self.organization)
        self.assertIn(self.responder, service_form.fields["owner"].queryset)
        self.assertNotIn(self.viewer, service_form.fields["owner"].queryset)
        self.assertNotIn(self.other_owner, service_form.fields["owner"].queryset)
        incident_form = IncidentForm(organization=self.organization)
        self.assertIn(self.service, incident_form.fields["service"].queryset)
        self.assertNotIn(self.other_service, incident_form.fields["service"].queryset)
        action_form = ActionItemForm(organization=self.organization)
        self.assertIn(self.viewer, action_form.fields["owner"].queryset)
        self.assertNotIn(self.other_owner, action_form.fields["owner"].queryset)

    def test_service_form_normalizes_and_rejects_duplicate_slug(self):
        form = ServiceForm(
            {
                "name": "New API",
                "slug": "New-API",
                "description": "",
                "status": Service.Status.OPERATIONAL,
                "owner": self.owner.pk,
                "public": True,
            },
            organization=self.organization,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["slug"], "new-api")
        form = ServiceForm(
            {
                "name": "Duplicate",
                "slug": "API",
                "description": "",
                "status": Service.Status.OPERATIONAL,
                "owner": self.owner.pk,
                "public": True,
            },
            organization=self.organization,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("slug", form.errors)

    def test_update_form_transitions_and_resolution_gate(self):
        form = IncidentUpdateForm(
            {
                "status": Incident.Status.IDENTIFIED,
                "message": "Root cause found.",
                "public": True,
            },
            incident=self.incident,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form = IncidentUpdateForm(
            {"status": Incident.Status.RESOLVED, "message": "Fixed."},
            incident=self.incident,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("resolution_summary", form.errors)

    def test_responder_form_excludes_assigned_and_other_tenants(self):
        form = ResponderForm(
            organization=self.organization,
            incident=self.incident,
        )
        self.assertNotIn(self.commander, form.fields["user"].queryset)
        self.assertIn(self.responder, form.fields["user"].queryset)
        self.assertNotIn(self.viewer, form.fields["user"].queryset)
        self.assertNotIn(self.other_owner, form.fields["user"].queryset)

    def test_dashboard_is_tenant_scoped(self):
        self.login()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elevated errors")
        self.assertNotContains(response, "Other API")
        self.assertEqual(response.context["active_count"], 1)
        self.assertEqual(response.context["resolved_count"], 1)
        self.assertEqual(response.context["mttr"], 40)

    def test_service_list_filters_search_and_status(self):
        self.login()
        response = self.client.get(
            reverse("service_list"), {"q": "customer", "status": "operational"}
        )
        self.assertContains(response, "API")
        self.assertNotContains(response, "Other API")

    def test_viewer_cannot_create_or_edit_service(self):
        self.login(self.viewer)
        self.assertEqual(self.client.get(reverse("service_create")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("service_edit", args=[self.service.pk])).status_code,
            403,
        )

    def test_manager_creates_and_edits_service(self):
        self.login(self.commander)
        response = self.client.post(
            reverse("service_create"),
            {
                "name": "Webhooks",
                "slug": "webhooks",
                "description": "Outbound webhooks",
                "status": Service.Status.OPERATIONAL,
                "owner": self.responder.pk,
                "public": True,
            },
        )
        self.assertRedirects(response, reverse("service_list"))
        service = Service.objects.get(slug="webhooks")
        response = self.client.post(
            reverse("service_edit", args=[service.pk]),
            {
                "name": "Event webhooks",
                "slug": "webhooks",
                "description": "Outbound events",
                "status": Service.Status.MAINTENANCE,
                "owner": self.responder.pk,
                "public": True,
            },
        )
        self.assertRedirects(response, reverse("service_list"))
        service.refresh_from_db()
        self.assertEqual(service.name, "Event webhooks")

    def test_service_edit_cannot_access_other_tenant(self):
        self.login()
        response = self.client.get(reverse("service_edit", args=[self.other_service.pk]))
        self.assertEqual(response.status_code, 404)

    def test_incident_list_filters_and_is_tenant_scoped(self):
        self.login()
        response = self.client.get(
            reverse("incident_list"),
            {"q": "elevated", "status": "investigating", "severity": "sev2"},
        )
        self.assertContains(response, "Elevated errors")
        response = self.client.get(reverse("incident_list"), {"service": self.other_service.pk})
        self.assertNotContains(response, "Other API")

    def test_viewer_cannot_declare_incident(self):
        self.login(self.viewer)
        self.assertEqual(self.client.get(reverse("incident_create")).status_code, 403)

    def test_responder_declares_incident_atomically(self):
        self.login(self.responder)
        started = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(
            reverse("incident_create"),
            {
                "service": self.service.pk,
                "title": "Queue saturation",
                "severity": Incident.Severity.SEV1,
                "summary": "Workers are saturated.",
                "customer_impact": "Jobs are delayed.",
                "commander": self.commander.pk,
                "started_at": started,
            },
        )
        incident = Incident.objects.get(title="Queue saturation")
        self.assertRedirects(response, reverse("incident_detail", args=[incident.pk]))
        self.assertTrue(incident.responders.filter(user=self.commander).exists())
        self.assertTrue(incident.updates.filter(public=True).exists())
        self.service.refresh_from_db()
        self.assertEqual(self.service.status, Service.Status.MAJOR_OUTAGE)

    def test_incident_detail_and_api_cannot_cross_tenants(self):
        other_incident = Incident.objects.create(
            organization=self.other_organization,
            service=self.other_service,
            title="Other incident",
            summary="Other",
            commander=self.other_owner,
            created_by=self.other_owner,
        )
        self.login()
        self.assertEqual(
            self.client.get(reverse("incident_detail", args=[other_incident.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("api_incident_detail", args=[other_incident.pk])).status_code,
            404,
        )

    def test_responder_posts_update_and_changes_status(self):
        self.login(self.responder)
        response = self.client.post(
            reverse("incident_update", args=[self.incident.pk]),
            {
                "status": Incident.Status.IDENTIFIED,
                "message": "A failing pool was isolated.",
                "public": True,
            },
        )
        self.assertRedirects(response, reverse("incident_detail", args=[self.incident.pk]))
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, Incident.Status.IDENTIFIED)
        self.assertTrue(self.incident.updates.filter(message__contains="failing pool").exists())

    def test_invalid_update_does_not_change_incident(self):
        self.login(self.responder)
        count = self.incident.updates.count()
        self.client.post(
            reverse("incident_update", args=[self.incident.pk]),
            {
                "status": Incident.Status.RESOLVED,
                "message": "Fixed without details.",
            },
        )
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, Incident.Status.INVESTIGATING)
        self.assertEqual(self.incident.updates.count(), count)

    def test_resolving_incident_recovers_service(self):
        self.service.status = Service.Status.PARTIAL_OUTAGE
        self.service.save()
        self.login(self.commander)
        self.client.post(
            reverse("incident_update", args=[self.incident.pk]),
            {
                "status": Incident.Status.RESOLVED,
                "message": "Traffic is healthy.",
                "public": True,
                "resolution_summary": "Removed the unhealthy backend pool.",
            },
        )
        self.incident.refresh_from_db()
        self.service.refresh_from_db()
        self.assertEqual(self.incident.status, Incident.Status.RESOLVED)
        self.assertIsNotNone(self.incident.resolved_at)
        self.assertEqual(self.service.status, Service.Status.OPERATIONAL)

    def test_viewer_cannot_update_and_resolved_is_read_only(self):
        self.login(self.viewer)
        self.assertEqual(
            self.client.post(
                reverse("incident_update", args=[self.incident.pk]),
                {"status": "identified", "message": "No"},
            ).status_code,
            403,
        )
        self.login(self.owner)
        self.assertEqual(
            self.client.post(
                reverse("incident_update", args=[self.resolved.pk]),
                {"status": "resolved", "message": "No"},
            ).status_code,
            403,
        )

    def test_commander_assigns_responder(self):
        self.login(self.commander)
        response = self.client.post(
            reverse("incident_responder_add", args=[self.incident.pk]),
            {"user": self.responder.pk, "responsibility": "Database response"},
        )
        self.assertRedirects(response, reverse("incident_detail", args=[self.incident.pk]))
        self.assertTrue(self.incident.responders.filter(user=self.responder).exists())
        self.assertTrue(self.incident.updates.filter(message__contains="joined response").exists())

    def test_non_commander_cannot_assign_responder(self):
        self.login(self.responder)
        response = self.client.post(
            reverse("incident_responder_add", args=[self.incident.pk]),
            {"user": self.responder.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_cannot_assign_responder_to_resolved_incident(self):
        self.login(self.owner)
        response = self.client.post(
            reverse("incident_responder_add", args=[self.resolved.pk]),
            {"user": self.responder.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_responder_adds_action_and_viewer_cannot(self):
        self.login(self.responder)
        response = self.client.post(
            reverse("incident_action_add", args=[self.incident.pk]),
            {
                "title": "Add load test",
                "owner": self.viewer.pk,
                "due_date": timezone.localdate() + timedelta(days=2),
            },
        )
        self.assertRedirects(response, reverse("incident_detail", args=[self.incident.pk]))
        self.assertTrue(self.incident.action_items.filter(title="Add load test").exists())
        self.login(self.viewer)
        response = self.client.post(
            reverse("incident_action_add", args=[self.incident.pk]),
            {"title": "Forbidden", "owner": self.viewer.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_action_owner_toggles_completion(self):
        self.login(self.responder)
        response = self.client.post(
            reverse("incident_action_toggle", args=[self.incident.pk, self.action.pk])
        )
        self.assertRedirects(response, reverse("incident_detail", args=[self.incident.pk]))
        self.action.refresh_from_db()
        self.assertEqual(self.action.status, ActionItem.Status.COMPLETED)
        self.assertIsNotNone(self.action.completed_at)
        self.client.post(reverse("incident_action_toggle", args=[self.incident.pk, self.action.pk]))
        self.action.refresh_from_db()
        self.assertEqual(self.action.status, ActionItem.Status.OPEN)
        self.assertIsNone(self.action.completed_at)

    def test_unrelated_viewer_cannot_toggle_action(self):
        self.login(self.viewer)
        response = self.client.post(
            reverse("incident_action_toggle", args=[self.incident.pk, self.action.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_resolved_incident_actions_are_read_only(self):
        action = ActionItem.objects.create(
            organization=self.organization,
            incident=self.resolved,
            title="Preserved follow-up",
            owner=self.owner,
        )
        self.login(self.owner)
        self.assertEqual(
            self.client.post(
                reverse("incident_action_add", args=[self.resolved.pk]),
                {"title": "Late mutation", "owner": self.owner.pk},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("incident_action_toggle", args=[self.resolved.pk, action.pk])
            ).status_code,
            403,
        )

    def test_public_status_hides_internal_and_private_content(self):
        private = Service.objects.create(
            organization=self.organization,
            name="Internal admin",
            slug="internal-admin",
            owner=self.owner,
            public=False,
        )
        response = self.client.get(reverse("public_status", args=[self.organization.slug]))
        self.assertContains(response, "We are investigating")
        self.assertNotContains(response, "Internal trace identifier")
        self.assertNotContains(response, private.name)
        self.assertNotContains(response, "Other API")

    def test_disabled_status_page_returns_404(self):
        self.organization.status_page_enabled = False
        self.organization.save()
        response = self.client.get(reverse("public_status", args=[self.organization.slug]))
        self.assertEqual(response.status_code, 404)

    def test_service_status_recalculation_prioritizes_severity(self):
        low = Incident.objects.create(
            organization=self.organization,
            service=self.service,
            title="Low severity",
            severity=Incident.Severity.SEV4,
            summary="Low",
            commander=self.owner,
            created_by=self.owner,
        )
        self.assertEqual(recalculate_service_status(self.service), Service.Status.PARTIAL_OUTAGE)
        self.incident.severity = Incident.Severity.SEV1
        self.incident.save()
        self.assertEqual(recalculate_service_status(self.service), Service.Status.MAJOR_OUTAGE)
        low.status = Incident.Status.RESOLVED
        low.resolution_summary = "Done"
        low.resolved_at = timezone.now()
        low.save()

    def test_recalculation_preserves_manual_maintenance(self):
        self.incident.status = Incident.Status.RESOLVED
        self.incident.resolution_summary = "Done"
        self.incident.resolved_at = timezone.now()
        self.incident.save()
        self.service.status = Service.Status.MAINTENANCE
        self.service.save()
        self.assertEqual(recalculate_service_status(self.service), Service.Status.MAINTENANCE)

    def test_api_summary_is_authenticated_and_tenant_scoped(self):
        self.assertEqual(self.client.get(reverse("api_summary")).status_code, 302)
        self.login(self.viewer)
        payload = self.client.get(reverse("api_summary")).json()
        self.assertEqual(payload["workspace"], "Northstar")
        self.assertEqual(payload["role"], Membership.Role.VIEWER)
        self.assertEqual(payload["services"], 1)
        self.assertEqual(payload["active_incidents"], 1)
        self.assertEqual(payload["resolved_last_30_days"], 1)

    def test_services_api_returns_tenant_metrics(self):
        self.login()
        payload = self.client.get(reverse("api_services")).json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["name"], "API")
        self.assertEqual(payload["results"][0]["active_incidents"], 1)

    def test_incident_api_filters_and_detail(self):
        self.login()
        payload = self.client.get(
            reverse("api_incidents"),
            {"status": "investigating", "severity": "sev2"},
        ).json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["title"], "Elevated errors")
        detail = self.client.get(reverse("api_incident_detail", args=[self.incident.pk])).json()
        self.assertEqual(detail["service"], "API")
        self.assertEqual(len(detail["responders"]), 1)
        self.assertEqual(len(detail["updates"]), 2)
        self.assertEqual(len(detail["actions"]), 1)
        self.assertTrue(detail["actions"][0]["overdue"])

    def test_seed_demo_is_idempotent_and_accounts_authenticate(self):
        call_command("seed_demo", verbosity=0)
        counts = (
            Organization.objects.count(),
            Service.objects.count(),
            Incident.objects.count(),
            IncidentUpdate.objects.count(),
            ActionItem.objects.count(),
        )
        call_command("seed_demo", verbosity=0)
        self.assertEqual(
            counts,
            (
                Organization.objects.count(),
                Service.objects.count(),
                Incident.objects.count(),
                IncidentUpdate.objects.count(),
                ActionItem.objects.count(),
            ),
        )
        self.assertTrue(self.client.login(username="demo_ops", password="DemoPass123!"))
        self.assertContains(self.client.get(reverse("dashboard")), "Elevated API")
