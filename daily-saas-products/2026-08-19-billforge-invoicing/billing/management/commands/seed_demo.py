from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from billing.models import Client, Invoice, LineItem, Membership, Organization, Payment


class Command(BaseCommand):
    help = "Create or reset a safe local BillForge demo workspace"

    @transaction.atomic
    def handle(self, *args, **options):
        user, _ = User.objects.get_or_create(username="demo_billing", defaults={"email": "demo@billforge.local"})
        user.set_password("DemoPass123!")
        user.save()
        org, _ = Organization.objects.get_or_create(
            slug="northstar-creative", defaults={"name": "Northstar Creative", "tax_id": "GSTIN-DEMO-29ABCDE1234F1Z5"}
        )
        Membership.objects.update_or_create(user=user, defaults={"organization": org, "role": Membership.Role.OWNER})
        Payment.objects.filter(organization=org).delete()
        Invoice.objects.filter(organization=org).delete()
        Client.objects.filter(organization=org).delete()
        clients = [
            Client.objects.create(organization=org, name=n, company=c, email=e)
            for n, c, e in [
                ("Riya Mehta", "BrightLabs", "riya@example.com"),
                ("Arjun Kapoor", "Mosaic Retail", "arjun@example.com"),
                ("Meera Rao", "GreenGrid", "meera@example.com"),
            ]
        ]
        today = timezone.localdate()
        inv1 = Invoice.objects.create(
            organization=org,
            client=clients[0],
            number="BF-1042",
            issue_date=today,
            due_date=today + timedelta(days=14),
            status="sent",
            tax_rate=18,
        )
        LineItem.objects.create(invoice=inv1, description="Product design sprint", quantity=1, unit_price=Decimal("180000"))
        LineItem.objects.create(invoice=inv1, description="Development handoff", quantity=1, unit_price=Decimal("65000"))
        Payment.objects.create(organization=org, invoice=inv1, amount=Decimal("100000"), method="Bank transfer", reference="UTR-DEMO-1001")
        inv2 = Invoice.objects.create(
            organization=org,
            client=clients[1],
            number="BF-1041",
            issue_date=today - timedelta(days=30),
            due_date=today - timedelta(days=15),
            status="sent",
            tax_rate=18,
        )
        LineItem.objects.create(invoice=inv2, description="E-commerce analytics dashboard", quantity=1, unit_price=Decimal("125000"))
        inv3 = Invoice.objects.create(
            organization=org,
            client=clients[2],
            number="BF-1040",
            issue_date=today - timedelta(days=25),
            due_date=today - timedelta(days=10),
            status="paid",
            tax_rate=18,
        )
        LineItem.objects.create(invoice=inv3, description="Monthly product retainer", quantity=1, unit_price=Decimal("80000"))
        Payment.objects.create(organization=org, invoice=inv3, amount=inv3.total, method="UPI")
        self.stdout.write(self.style.SUCCESS("Demo ready: demo_billing / DemoPass123!"))
