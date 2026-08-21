from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from scheduler.models import Appointment, Customer, Membership, Organization, Service


class Command(BaseCommand):
    help = "Create or refresh a safe local SlotNest demonstration workspace."

    def handle(self, *args, **options):
        user, _ = User.objects.get_or_create(
            username="demo_scheduler",
            defaults={"email": "demo@slotnest.local", "first_name": "Mira"},
        )
        user.set_password("DemoPass123!")
        user.save()
        organization, _ = Organization.objects.get_or_create(
            slug="northstar-wellness", defaults={"name": "Northstar Wellness"}
        )
        Membership.objects.update_or_create(
            user=user,
            defaults={"organization": organization, "role": Membership.Role.OWNER},
        )

        service_specs = [
            ("Initial consultation", 60, "1800.00", "#357a68"),
            ("Strategy session", 90, "3200.00", "#db7657"),
            ("Progress review", 45, "1200.00", "#d6a83e"),
        ]
        services = {}
        for name, duration, price, color in service_specs:
            services[name], _ = Service.objects.update_or_create(
                organization=organization,
                name=name,
                defaults={
                    "duration_minutes": duration,
                    "price": Decimal(price),
                    "color": color,
                    "active": True,
                },
            )

        customer_specs = [
            ("Anika Rao", "anika@example.com", "+91 98765 01001"),
            ("Kabir Shah", "kabir@example.com", "+91 98765 01002"),
            ("Leena Thomas", "leena@example.com", "+91 98765 01003"),
        ]
        customers = {}
        for name, email, phone in customer_specs:
            customers[name], _ = Customer.objects.update_or_create(
                organization=organization,
                email=email,
                defaults={"name": name, "phone": phone},
            )

        today = timezone.localdate()
        rows = [
            ("Anika Rao", "Initial consultation", time(9, 30), Appointment.Status.COMPLETED),
            ("Kabir Shah", "Strategy session", time(11, 0), Appointment.Status.CHECKED_IN),
            ("Leena Thomas", "Progress review", time(14, 30), Appointment.Status.CONFIRMED),
        ]
        for customer_name, service_name, clock, status in rows:
            starts_at = timezone.make_aware(datetime.combine(today, clock))
            Appointment.objects.update_or_create(
                organization=organization,
                staff=user,
                starts_at=starts_at,
                defaults={
                    "customer": customers[customer_name],
                    "service": services[service_name],
                    "status": status,
                    "notes": "Created by the repeatable SlotNest demo-data command.",
                },
            )
        tomorrow = timezone.make_aware(datetime.combine(today + timedelta(days=1), time(10, 0)))
        Appointment.objects.update_or_create(
            organization=organization,
            staff=user,
            starts_at=tomorrow,
            defaults={
                "customer": customers["Anika Rao"],
                "service": services["Progress review"],
                "status": Appointment.Status.CONFIRMED,
            },
        )
        self.stdout.write(self.style.SUCCESS("SlotNest demo ready: demo_scheduler / DemoPass123!"))
