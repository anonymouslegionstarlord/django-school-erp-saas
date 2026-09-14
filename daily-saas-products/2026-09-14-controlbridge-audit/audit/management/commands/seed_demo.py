from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from audit.models import AuditFinding, ControlArea, FindingEvent, Membership, Organization, RemediationTask


class Command(BaseCommand):
    help = "Create an idempotent ControlBridge demo workspace"

    def handle(self, *args, **options):
        org, _ = Organization.objects.update_or_create(slug="northstar-digital", defaults={"name": "Northstar Digital"})
        users = {}
        for username, role in [
            ("demo_control", Membership.Role.OWNER),
            ("demo_control_manager", Membership.Role.MANAGER),
            ("demo_control_auditor", Membership.Role.ANALYST),
            ("demo_control_viewer", Membership.Role.VIEWER),
        ]:
            user, _ = User.objects.update_or_create(username=username, defaults={"email": f"{username}@example.com"})
            user.set_password("DemoPass123!")
            user.save()
            Membership.objects.update_or_create(user=user, defaults={"organization": org, "role": role})
            users[role] = user
        control_areas = {}
        for name, email, department in [
            ("Access Governance", "access.owner@example.com", "IT Security"),
            ("Revenue Recognition", "finance.owner@example.com", "Finance"),
            ("Vendor Assurance", "vendor.owner@example.com", "Procurement"),
        ]:
            control_area, _ = ControlArea.objects.update_or_create(
                organization=org, email=email, defaults={"name": name, "department": department}
            )
            control_areas[email] = control_area
        now = timezone.now()
        specs = [
            (
                "AUD-DEMO-CONTROL_GAP",
                "access.owner@example.com",
                AuditFinding.Kind.CONTROL_GAP,
                AuditFinding.Framework.ISO27001,
                AuditFinding.Status.REMEDIATION,
                now + timedelta(days=12),
            ),
            (
                "AUD-DEMO-DELETE",
                "finance.owner@example.com",
                AuditFinding.Kind.POLICY_BREACH,
                AuditFinding.Framework.SOX,
                AuditFinding.Status.TRIAGE,
                now - timedelta(days=2),
            ),
            (
                "AUD-DEMO-PORTABLE",
                "vendor.owner@example.com",
                AuditFinding.Kind.EVIDENCE_GAP,
                AuditFinding.Framework.SOC2,
                AuditFinding.Status.REVIEW,
                now + timedelta(days=5),
            ),
        ]
        for code, email, kind, framework, status, due in specs:
            item, _ = AuditFinding.objects.update_or_create(
                tracking_code=code,
                defaults={
                    "organization": org,
                    "control_area": control_areas[email],
                    "kind": kind,
                    "framework": framework,
                    "status": status,
                    "description": "Testing identified a control exception requiring documented remediation and evidence.",
                    "received_at": now - timedelta(days=8),
                    "due_at": due,
                    "assigned_to": users[Membership.Role.ANALYST],
                    "created_by": users[Membership.Role.MANAGER],
                    "triaged_at": now - timedelta(days=6) if status not in {AuditFinding.Status.OPEN, AuditFinding.Status.TRIAGE} else None,
                },
            )
            item.tasks.all().delete()
            if status in {AuditFinding.Status.REMEDIATION, AuditFinding.Status.REVIEW}:
                for title, done in [("Document root cause", True), ("Attach control evidence", status == AuditFinding.Status.REVIEW)]:
                    RemediationTask.objects.create(
                        finding=item,
                        title=title,
                        assignee=users[Membership.Role.ANALYST],
                        due_at=due - timedelta(days=2),
                        status=RemediationTask.Status.DONE if done else RemediationTask.Status.WORKING,
                        completed_at=now if done else None,
                    )
            item.events.all().delete()
            FindingEvent.objects.create(
                finding=item,
                actor=users[Membership.Role.MANAGER],
                message="Finding logged and remediation deadline confirmed.",
                visible_to_stakeholders=True,
            )
        self.stdout.write(self.style.SUCCESS("ControlBridge demo workspace is ready."))
