from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from crm.models import Activity, Contact, Deal, Membership, Organization


class Command(BaseCommand):
    help = "Create or reset a safe local ClientFlow demo workspace"

    @transaction.atomic
    def handle(self, *args, **options):
        user, _ = User.objects.get_or_create(username="demo_owner", defaults={"email": "demo@clientflow.local"})
        user.set_password("DemoPass123!")
        user.save()
        organization, _ = Organization.objects.get_or_create(slug="northstar-studio", defaults={"name": "Northstar Studio"})
        Membership.objects.update_or_create(user=user, defaults={"organization": organization, "role": Membership.Role.OWNER})
        Activity.objects.filter(organization=organization).delete()
        Deal.objects.filter(organization=organization).delete()
        Contact.objects.filter(organization=organization).delete()
        rows = [
            ("Aarav Mehta", "BrightLabs", "aarav@example.com", "+91 98765 10001"),
            ("Nisha Kapoor", "Mosaic Retail", "nisha@example.com", "+91 98765 10002"),
            ("Kabir Sharma", "UrbanDesk", "kabir@example.com", "+91 98765 10003"),
            ("Meera Iyer", "GreenGrid", "meera@example.com", "+91 98765 10004"),
        ]
        contacts = [
            Contact.objects.create(organization=organization, name=name, company=company, email=email, phone=phone)
            for name, company, email, phone in rows
        ]
        deals = [
            Deal.objects.create(
                organization=organization,
                contact=contacts[0],
                title="Brand website redesign",
                value=Decimal("240000"),
                stage=Deal.Stage.PROPOSAL,
                expected_close=date.today() + timedelta(days=12),
            ),
            Deal.objects.create(
                organization=organization,
                contact=contacts[1],
                title="Retail analytics dashboard",
                value=Decimal("325000"),
                stage=Deal.Stage.QUALIFIED,
                expected_close=date.today() + timedelta(days=20),
            ),
            Deal.objects.create(
                organization=organization,
                contact=contacts[2],
                title="Annual support plan",
                value=Decimal("180000"),
                stage=Deal.Stage.LEAD,
                expected_close=date.today() + timedelta(days=30),
            ),
            Deal.objects.create(
                organization=organization,
                contact=contacts[3],
                title="Customer portal MVP",
                value=Decimal("410000"),
                stage=Deal.Stage.WON,
                expected_close=date.today(),
            ),
        ]
        Activity.objects.create(
            organization=organization,
            deal=deals[0],
            kind=Activity.Kind.MEETING,
            notes="Presented the visual direction and agreed on the proposal scope.",
            created_by=user,
        )
        Activity.objects.create(
            organization=organization,
            deal=deals[1],
            kind=Activity.Kind.CALL,
            notes="Discovery call completed; data sources documented.",
            created_by=user,
        )
        self.stdout.write(self.style.SUCCESS("Demo ready: demo_owner / DemoPass123!"))
