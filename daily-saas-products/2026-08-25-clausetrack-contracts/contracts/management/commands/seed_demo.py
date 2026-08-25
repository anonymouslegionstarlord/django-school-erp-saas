from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from contracts.models import Activity, Contract, Counterparty, Membership, Obligation, Organization


class Command(BaseCommand):
    help = "Create an idempotent ClauseTrack demo workspace"

    def handle(self, *args, **options):
        password = "DemoPass123!"
        organization, _ = Organization.objects.get_or_create(
            slug="meridian-labs", defaults={"name": "Meridian Labs"}
        )
        users = {}
        for username, role, email in [
            ("demo_contracts", Membership.Role.OWNER, "contracts@example.com"),
            ("demo_legal", Membership.Role.LEGAL, "legal@example.com"),
            ("demo_viewer", Membership.Role.VIEWER, "viewer@example.com"),
        ]:
            user, _ = User.objects.get_or_create(username=username, defaults={"email": email})
            user.set_password(password)
            user.save()
            Membership.objects.update_or_create(
                user=user, defaults={"organization": organization, "role": role}
            )
            users[username] = user
        counterparties = {}
        for name, email, contact in [
            ("Northstar Cloud", "legal@northstar.example", "Aisha Rao"),
            ("Cedar Works", "ops@cedar.example", "Kabir Shah"),
            ("Atlas Realty", "lease@atlas.example", "Maya Iyer"),
        ]:
            item, _ = Counterparty.objects.update_or_create(
                organization=organization,
                email=email,
                defaults={"name": name, "contact_name": contact},
            )
            counterparties[name] = item
        today = timezone.localdate()
        rows = [
            (
                "VEN-1042",
                "Cloud platform agreement",
                "Northstar Cloud",
                Contract.Kind.VENDOR,
                Contract.Status.ACTIVE,
                today - timedelta(days=330),
                today + timedelta(days=24),
                Decimal("840000"),
                45,
                True,
            ),
            (
                "CUS-2108",
                "Enterprise services agreement",
                "Cedar Works",
                Contract.Kind.CUSTOMER,
                Contract.Status.ACTIVE,
                today - timedelta(days=100),
                today + timedelta(days=265),
                Decimal("1250000"),
                60,
                False,
            ),
            (
                "NDA-0314",
                "Mutual confidentiality agreement",
                "Cedar Works",
                Contract.Kind.NDA,
                Contract.Status.REVIEW,
                today,
                today + timedelta(days=730),
                Decimal("0"),
                30,
                False,
            ),
            (
                "LSE-0903",
                "Bengaluru office lease",
                "Atlas Realty",
                Contract.Kind.LEASE,
                Contract.Status.EXPIRED,
                today - timedelta(days=760),
                today - timedelta(days=30),
                Decimal("390000"),
                90,
                False,
            ),
        ]
        contracts = {}
        for reference, title, party, kind, status, start, end, value, notice, renew in rows:
            item, _ = Contract.objects.update_or_create(
                organization=organization,
                reference=reference,
                defaults={
                    "title": title,
                    "counterparty": counterparties[party],
                    "kind": kind,
                    "status": status,
                    "starts_on": start,
                    "ends_on": end,
                    "value": value,
                    "notice_days": notice,
                    "auto_renew": renew,
                    "owner": users["demo_legal"],
                    "summary": (
                        "Demo agreement showing lifecycle dates, financial exposure, "
                        "ownership, and compliance obligations."
                    ),
                },
            )
            contracts[reference] = item
        for reference, title, due, assignee in [
            ("VEN-1042", "Send non-renewal decision", today + timedelta(days=7), "demo_legal"),
            (
                "VEN-1042",
                "Complete annual security review",
                today - timedelta(days=5),
                "demo_contracts",
            ),
            (
                "CUS-2108",
                "Deliver quarterly service report",
                today + timedelta(days=18),
                "demo_viewer",
            ),
        ]:
            Obligation.objects.update_or_create(
                organization=organization,
                contract=contracts[reference],
                title=title,
                defaults={"due_on": due, "assigned_to": users[assignee]},
            )
        for reference, message in [
            ("VEN-1042", "Renewal window opened"),
            ("CUS-2108", "Commercial terms approved"),
        ]:
            Activity.objects.get_or_create(
                organization=organization,
                contract=contracts[reference],
                author=users["demo_legal"],
                message=message,
            )
        self.stdout.write(
            self.style.SUCCESS("ClauseTrack demo ready: demo_contracts / DemoPass123!")
        )
