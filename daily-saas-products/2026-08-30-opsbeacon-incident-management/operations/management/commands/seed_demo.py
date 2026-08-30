from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from operations.models import (
    ActionItem,
    Incident,
    IncidentResponder,
    IncidentUpdate,
    Membership,
    Organization,
    Service,
)


class Command(BaseCommand):
    help = "Create or refresh the idempotent OpsBeacon demonstration workspace."

    password = "DemoPass123!"

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        today = timezone.localdate()
        organization, _ = Organization.objects.update_or_create(
            slug="northstar-digital",
            defaults={
                "name": "Northstar Digital Operations",
                "status_page_enabled": True,
            },
        )

        users = {
            "owner": self._user(
                organization,
                username="demo_ops",
                first_name="Maya",
                last_name="Chen",
                email="maya@example.com",
                role=Membership.Role.OWNER,
                team="Reliability",
                title="VP, Engineering",
            ),
            "commander": self._user(
                organization,
                username="demo_commander",
                first_name="Noah",
                last_name="Williams",
                email="noah@example.com",
                role=Membership.Role.COMMANDER,
                team="Site Reliability",
                title="Incident commander",
            ),
            "responder": self._user(
                organization,
                username="demo_responder",
                first_name="Priya",
                last_name="Shah",
                email="priya@example.com",
                role=Membership.Role.RESPONDER,
                team="Platform",
                title="Senior platform engineer",
            ),
            "viewer": self._user(
                organization,
                username="demo_observer",
                first_name="Eli",
                last_name="Brooks",
                email="eli@example.com",
                role=Membership.Role.VIEWER,
                team="Customer success",
                title="Support lead",
            ),
        }

        services = {
            "api": self._service(
                organization,
                users["responder"],
                name="Customer API",
                slug="customer-api",
                description="Public REST and GraphQL endpoints used by customer apps.",
                status=Service.Status.PARTIAL_OUTAGE,
            ),
            "checkout": self._service(
                organization,
                users["commander"],
                name="Web checkout",
                slug="web-checkout",
                description="Hosted checkout, tax calculation, and payment orchestration.",
                status=Service.Status.DEGRADED,
            ),
            "identity": self._service(
                organization,
                users["owner"],
                name="Identity and login",
                slug="identity-login",
                description="Authentication, single sign-on, and account sessions.",
                status=Service.Status.OPERATIONAL,
            ),
            "notifications": self._service(
                organization,
                users["responder"],
                name="Notifications",
                slug="notifications",
                description="Transactional email, SMS, and webhook delivery.",
                status=Service.Status.MAINTENANCE,
            ),
        }

        api_incident = self._incident(
            organization,
            services["api"],
            users["commander"],
            title="Elevated API error rate in APAC",
            severity=Incident.Severity.SEV2,
            status=Incident.Status.IDENTIFIED,
            summary=(
                "Requests routed through the Singapore edge are intermittently "
                "returning 502 responses."
            ),
            customer_impact=("Some APAC customers may see failed API requests and slower retries."),
            started_at=now - timedelta(minutes=95),
        )
        checkout_incident = self._incident(
            organization,
            services["checkout"],
            users["commander"],
            title="Intermittent checkout latency",
            severity=Incident.Severity.SEV3,
            status=Incident.Status.MONITORING,
            summary="A cache stampede increased p95 checkout response time.",
            customer_impact="A small number of shoppers may see a slower checkout.",
            started_at=now - timedelta(minutes=600),
        )
        login_incident = self._incident(
            organization,
            services["identity"],
            users["owner"],
            title="Login token refresh failures",
            severity=Incident.Severity.SEV1,
            status=Incident.Status.RESOLVED,
            summary="A key rotation caused token refresh requests to fail.",
            customer_impact="Some signed-in users were asked to authenticate again.",
            started_at=now - timedelta(days=2, minutes=45),
            resolved_at=now - timedelta(days=2),
            resolution_summary=(
                "Restored the previous signing key, refreshed edge caches, and "
                "added a rotation compatibility check."
            ),
        )

        self._responder(api_incident, users["commander"], "Incident commander")
        self._responder(api_incident, users["responder"], "Edge routing investigation")
        self._responder(checkout_incident, users["commander"], "Incident commander")
        self._responder(checkout_incident, users["responder"], "Application mitigation")
        self._responder(login_incident, users["owner"], "Incident commander")
        self._responder(login_incident, users["responder"], "Identity engineer")

        self._update(
            api_incident,
            users["commander"],
            "Investigating increased 502 responses from our Singapore edge.",
            Incident.Status.INVESTIGATING,
            public=True,
            created_at=now - timedelta(minutes=92),
        )
        self._update(
            api_incident,
            users["responder"],
            "Traffic traces point to an unhealthy upstream connection pool.",
            Incident.Status.IDENTIFIED,
            public=False,
            created_at=now - timedelta(minutes=61),
        )
        self._update(
            api_incident,
            users["commander"],
            "We isolated the affected pool and are shifting traffic to healthy capacity.",
            Incident.Status.IDENTIFIED,
            public=True,
            created_at=now - timedelta(minutes=28),
        )
        self._update(
            checkout_incident,
            users["commander"],
            "We identified excess cache misses affecting checkout latency.",
            Incident.Status.IDENTIFIED,
            public=True,
            created_at=now - timedelta(minutes=540),
        )
        self._update(
            checkout_incident,
            users["responder"],
            "Cache warm-up completed; response times are recovering.",
            Incident.Status.MONITORING,
            public=True,
            created_at=now - timedelta(minutes=35),
        )
        self._update(
            login_incident,
            users["owner"],
            "We are investigating failed session refreshes after a signing-key rotation.",
            Incident.Status.INVESTIGATING,
            public=True,
            created_at=login_incident.started_at + timedelta(minutes=3),
        )
        self._update(
            login_incident,
            users["responder"],
            "The previous key is restored and login sessions are healthy.",
            Incident.Status.RESOLVED,
            public=True,
            created_at=login_incident.resolved_at,
        )

        self._action(
            api_incident,
            users["responder"],
            "Add upstream pool saturation alert",
            today + timedelta(days=2),
        )
        self._action(
            checkout_incident,
            users["commander"],
            "Document cache warm-up runbook",
            today - timedelta(days=1),
        )
        self._action(
            login_incident,
            users["owner"],
            "Add preflight test to signing-key rotations",
            today - timedelta(days=1),
            completed=True,
        )

        self.stdout.write(self.style.SUCCESS("OpsBeacon demo workspace is ready."))
        self.stdout.write("Status page: /status/northstar-digital/")
        self.stdout.write("Password for every demo account: DemoPass123!")
        self.stdout.write("Users: demo_ops, demo_commander, demo_responder, demo_observer")

    def _user(
        self,
        organization,
        *,
        username,
        first_name,
        last_name,
        email,
        role,
        team,
        title,
    ):
        user, _ = User.objects.update_or_create(
            username=username,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "is_active": True,
            },
        )
        user.set_password(self.password)
        user.save(update_fields=["password"])
        Membership.objects.update_or_create(
            user=user,
            defaults={
                "organization": organization,
                "role": role,
                "team": team,
                "title": title,
            },
        )
        return user

    def _service(self, organization, owner, *, name, slug, description, status):
        service, _ = Service.objects.update_or_create(
            organization=organization,
            slug=slug,
            defaults={
                "name": name,
                "description": description,
                "status": status,
                "owner": owner,
                "public": True,
            },
        )
        service.full_clean()
        service.save()
        return service

    def _incident(
        self,
        organization,
        service,
        commander,
        *,
        title,
        severity,
        status,
        summary,
        customer_impact,
        started_at,
        resolved_at=None,
        resolution_summary="",
    ):
        incident, _ = Incident.objects.update_or_create(
            organization=organization,
            title=title,
            defaults={
                "service": service,
                "severity": severity,
                "status": status,
                "summary": summary,
                "customer_impact": customer_impact,
                "resolution_summary": resolution_summary,
                "commander": commander,
                "created_by": commander,
                "started_at": started_at,
                "resolved_at": resolved_at,
            },
        )
        incident.full_clean()
        incident.save()
        return incident

    def _responder(self, incident, user, responsibility):
        responder, _ = IncidentResponder.objects.update_or_create(
            incident=incident,
            user=user,
            defaults={
                "organization": incident.organization,
                "responsibility": responsibility,
            },
        )
        responder.full_clean()
        responder.save()

    def _update(
        self,
        incident,
        author,
        message,
        status,
        *,
        public,
        created_at,
    ):
        update, _ = IncidentUpdate.objects.update_or_create(
            incident=incident,
            message=message,
            defaults={
                "organization": incident.organization,
                "author": author,
                "status": status,
                "public": public,
            },
        )
        update.full_clean()
        update.save()
        IncidentUpdate.objects.filter(pk=update.pk).update(created_at=created_at)

    def _action(self, incident, owner, title, due_date, *, completed=False):
        action, _ = ActionItem.objects.update_or_create(
            incident=incident,
            title=title,
            defaults={
                "organization": incident.organization,
                "owner": owner,
                "due_date": due_date,
                "status": (ActionItem.Status.COMPLETED if completed else ActionItem.Status.OPEN),
                "completed_at": timezone.now() if completed else None,
            },
        )
        action.full_clean()
        action.save()
