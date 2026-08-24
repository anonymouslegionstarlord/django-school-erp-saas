from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from maintenance.models import Asset, Membership, Organization, Site, WorkLog, WorkOrder


class Command(BaseCommand):
    help = "Create or refresh a safe local MaintainIQ demonstration workspace."

    def handle(self, *args, **options):
        people = [
            ("demo_facilities", "Maya", "Iyer", Membership.Role.OWNER),
            ("demo_technician", "Arjun", "Das", Membership.Role.TECHNICIAN),
            ("demo_requester", "Sara", "Khan", Membership.Role.REQUESTER),
        ]
        users = {}
        organization, _ = Organization.objects.get_or_create(
            slug="helios-workspaces", defaults={"name": "Helios Workspaces"}
        )
        for username, first, last, role in people:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@maintainiq.local",
                    "first_name": first,
                    "last_name": last,
                },
            )
            user.set_password("DemoPass123!")
            user.save()
            Membership.objects.update_or_create(
                user=user, defaults={"organization": organization, "role": role}
            )
            users[role] = user
        hq, _ = Site.objects.update_or_create(
            organization=organization,
            name="Connaught Place Hub",
            defaults={
                "address": "Block A, Connaught Place, New Delhi",
                "contact_name": "Front desk",
                "contact_phone": "+91 98765 03001",
            },
        )
        studio, _ = Site.objects.update_or_create(
            organization=organization,
            name="Noida Studio",
            defaults={"address": "Sector 62, Noida", "contact_name": "Site manager"},
        )
        assets = {}
        specs = [
            (hq, "HVAC-01", "Main floor HVAC", "HVAC", Asset.Condition.WATCH),
            (hq, "LIFT-02", "Passenger lift B", "Vertical transport", Asset.Condition.GOOD),
            (studio, "GEN-04", "Backup generator", "Power", Asset.Condition.DOWN),
        ]
        for site, tag, name, category, condition in specs:
            assets[tag], _ = Asset.objects.update_or_create(
                organization=organization,
                tag=tag,
                defaults={"site": site, "name": name, "category": category, "condition": condition},
            )
        now = timezone.now()
        orders = [
            (
                "WO-2026-101",
                "HVAC airflow below target",
                hq,
                assets["HVAC-01"],
                WorkOrder.Priority.HIGH,
                WorkOrder.Status.IN_PROGRESS,
                now + timedelta(hours=8),
                users[Membership.Role.TECHNICIAN],
            ),
            (
                "WO-2026-102",
                "Generator failed weekly test",
                studio,
                assets["GEN-04"],
                WorkOrder.Priority.CRITICAL,
                WorkOrder.Status.ASSIGNED,
                now - timedelta(hours=2),
                users[Membership.Role.TECHNICIAN],
            ),
            (
                "WO-2026-103",
                "Replace meeting-room light",
                hq,
                None,
                WorkOrder.Priority.LOW,
                WorkOrder.Status.OPEN,
                now + timedelta(days=3),
                None,
            ),
        ]
        saved = {}
        for number, title, site, asset, priority, status, due_at, assigned in orders:
            saved[number], _ = WorkOrder.objects.update_or_create(
                organization=organization,
                number=number,
                defaults={
                    "title": title,
                    "description": "Created by the repeatable MaintainIQ demo-data command.",
                    "site": site,
                    "asset": asset,
                    "priority": priority,
                    "status": status,
                    "due_at": due_at,
                    "requested_by": users[Membership.Role.REQUESTER],
                    "assigned_to": assigned,
                },
            )
        WorkLog.objects.update_or_create(
            organization=organization,
            work_order=saved["WO-2026-101"],
            note="Inspected filters and measured supply airflow.",
            defaults={
                "author": users[Membership.Role.TECHNICIAN],
                "hours": Decimal("1.25"),
                "cost": Decimal("850.00"),
            },
        )
        self.stdout.write(
            self.style.SUCCESS("MaintainIQ demo ready: demo_facilities / DemoPass123!")
        )
