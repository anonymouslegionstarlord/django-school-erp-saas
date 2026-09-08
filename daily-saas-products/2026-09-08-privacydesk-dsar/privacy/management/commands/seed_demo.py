from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from privacy.models import DataSubject, Membership, Organization, PrivacyRequest, RequestEvent, RequestTask


class Command(BaseCommand):
    help = "Create an idempotent PrivacyDesk demo workspace"

    def handle(self, *args, **options):
        org, _ = Organization.objects.update_or_create(slug="northstar-digital", defaults={"name": "Northstar Digital"})
        users = {}
        for username, role in [
            ("demo_privacy", Membership.Role.OWNER),
            ("demo_privacy_manager", Membership.Role.MANAGER),
            ("demo_privacy_analyst", Membership.Role.ANALYST),
            ("demo_privacy_viewer", Membership.Role.VIEWER),
        ]:
            user, _ = User.objects.update_or_create(username=username, defaults={"email": f"{username}@example.com"})
            user.set_password("DemoPass123!")
            user.save()
            Membership.objects.update_or_create(user=user, defaults={"organization": org, "role": role})
            users[role] = user
        subjects = {}
        for name, email, country in [
            ("Aarav Mehta", "aarav@example.com", "India"),
            ("Elena Rossi", "elena@example.com", "Italy"),
            ("Jordan Lee", "jordan@example.com", "United States"),
        ]:
            subject, _ = DataSubject.objects.update_or_create(organization=org, email=email, defaults={"name": name, "country": country})
            subjects[email] = subject
        now = timezone.now()
        specs = [
            (
                "DSR-DEMO-ACCESS",
                "aarav@example.com",
                PrivacyRequest.Kind.ACCESS,
                PrivacyRequest.Jurisdiction.INDIA_DPDP,
                PrivacyRequest.Status.IN_PROGRESS,
                now + timedelta(days=12),
            ),
            (
                "DSR-DEMO-DELETE",
                "elena@example.com",
                PrivacyRequest.Kind.DELETION,
                PrivacyRequest.Jurisdiction.GDPR,
                PrivacyRequest.Status.VERIFYING,
                now - timedelta(days=2),
            ),
            (
                "DSR-DEMO-PORTABLE",
                "jordan@example.com",
                PrivacyRequest.Kind.PORTABILITY,
                PrivacyRequest.Jurisdiction.CCPA,
                PrivacyRequest.Status.REVIEW,
                now + timedelta(days=5),
            ),
        ]
        for code, email, kind, jurisdiction, status, due in specs:
            item, _ = PrivacyRequest.objects.update_or_create(
                tracking_code=code,
                defaults={
                    "organization": org,
                    "subject": subjects[email],
                    "kind": kind,
                    "jurisdiction": jurisdiction,
                    "status": status,
                    "description": "Customer requested a complete and secure privacy-rights response.",
                    "received_at": now - timedelta(days=8),
                    "due_at": due,
                    "assigned_to": users[Membership.Role.ANALYST],
                    "created_by": users[Membership.Role.MANAGER],
                    "identity_verified_at": now - timedelta(days=6)
                    if status not in {PrivacyRequest.Status.RECEIVED, PrivacyRequest.Status.VERIFYING}
                    else None,
                },
            )
            item.tasks.all().delete()
            if status in {PrivacyRequest.Status.IN_PROGRESS, PrivacyRequest.Status.REVIEW}:
                for title, done in [("Search customer platform", True), ("Review billing records", status == PrivacyRequest.Status.REVIEW)]:
                    RequestTask.objects.create(
                        request=item,
                        title=title,
                        assignee=users[Membership.Role.ANALYST],
                        due_at=due - timedelta(days=2),
                        status=RequestTask.Status.DONE if done else RequestTask.Status.WORKING,
                        completed_at=now if done else None,
                    )
            item.events.all().delete()
            RequestEvent.objects.create(
                request=item,
                actor=users[Membership.Role.MANAGER],
                message="Request received and deadline confirmed.",
                visible_to_subject=True,
            )
        self.stdout.write(self.style.SUCCESS("PrivacyDesk demo workspace is ready."))
