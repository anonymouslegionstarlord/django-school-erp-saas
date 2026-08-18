from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from support.models import Customer, Membership, Organization, Reply, Ticket


class Command(BaseCommand):
    help = "Create or reset a safe local DeskPulse demo workspace"

    @transaction.atomic
    def handle(self, *args, **options):
        owner, _ = User.objects.get_or_create(username="demo_agent", defaults={"email": "demo@deskpulse.local", "first_name": "Demo"})
        owner.set_password("DemoPass123!")
        owner.save()
        organization, _ = Organization.objects.get_or_create(slug="northstar-support", defaults={"name": "Northstar Support"})
        Membership.objects.update_or_create(user=owner, defaults={"organization": organization, "role": Membership.Role.OWNER})
        Reply.objects.filter(organization=organization).delete()
        Ticket.objects.filter(organization=organization).delete()
        Customer.objects.filter(organization=organization).delete()
        specs = [
            ("Riya Malhotra", "Acme Commerce", "riya@example.com"),
            ("Arjun Rao", "BrightLabs", "arjun@example.com"),
            ("Meera Singh", "Northwind Foods", "meera@example.com"),
            ("Kabir Jain", "UrbanDesk", "kabir@example.com"),
        ]
        customers = [
            Customer.objects.create(organization=organization, name=name, company=company, email=email) for name, company, email in specs
        ]
        tickets = [
            Ticket.objects.create(
                organization=organization,
                customer=customers[0],
                subject="Payment confirmation is missing",
                description="The payment completed successfully but the order is still marked unpaid.",
                category="Billing",
                priority=Ticket.Priority.URGENT,
                assigned_to=owner,
                due_at=timezone.now() + timedelta(minutes=75),
            ),
            Ticket.objects.create(
                organization=organization,
                customer=customers[1],
                subject="Unable to export the monthly report",
                description="CSV export stops after loading for several seconds.",
                category="Reports",
                priority=Ticket.Priority.HIGH,
                status=Ticket.Status.IN_PROGRESS,
                assigned_to=owner,
            ),
            Ticket.objects.create(
                organization=organization,
                customer=customers[2],
                subject="Update the billing contact",
                description="Please replace the old finance email for future invoices.",
                category="Account",
                priority=Ticket.Priority.LOW,
                status=Ticket.Status.WAITING,
            ),
            Ticket.objects.create(
                organization=organization,
                customer=customers[3],
                subject="Password reset email arrived",
                description="The reset link worked. Thank you for the quick support.",
                category="Access",
                priority=Ticket.Priority.MEDIUM,
                status=Ticket.Status.RESOLVED,
                assigned_to=owner,
            ),
        ]
        Reply.objects.create(
            organization=organization,
            ticket=tickets[0],
            author=owner,
            body="I am checking the payment gateway event and will update you shortly.",
        )
        Reply.objects.create(
            organization=organization,
            ticket=tickets[1],
            author=owner,
            body="The export worker is timing out on large date ranges.",
            internal=True,
        )
        self.stdout.write(self.style.SUCCESS("Demo ready: demo_agent / DemoPass123!"))
