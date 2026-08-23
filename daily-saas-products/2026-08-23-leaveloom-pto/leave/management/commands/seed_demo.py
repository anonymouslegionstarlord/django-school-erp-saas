from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from leave.models import LeaveRequest, LeaveType, Membership, Organization


class Command(BaseCommand):
    help = "Create or refresh a safe local LeaveLoom demonstration workspace."

    def handle(self, *args, **options):
        owner, _ = User.objects.get_or_create(
            username="demo_peopleops",
            defaults={
                "email": "peopleops@leaveloom.local",
                "first_name": "Priya",
                "last_name": "Menon",
            },
        )
        owner.set_password("DemoPass123!")
        owner.save()
        employee, _ = User.objects.get_or_create(
            username="demo_employee",
            defaults={
                "email": "employee@leaveloom.local",
                "first_name": "Rohan",
                "last_name": "Kapoor",
            },
        )
        employee.set_password("DemoPass123!")
        employee.save()
        manager, _ = User.objects.get_or_create(
            username="demo_manager",
            defaults={
                "email": "manager@leaveloom.local",
                "first_name": "Neha",
                "last_name": "Singh",
            },
        )
        manager.set_password("DemoPass123!")
        manager.save()
        organization, _ = Organization.objects.get_or_create(
            slug="northstar-digital", defaults={"name": "Northstar Digital"}
        )
        Membership.objects.update_or_create(
            user=owner,
            defaults={
                "organization": organization,
                "role": Membership.Role.OWNER,
                "job_title": "People operations lead",
                "annual_allowance": 24,
            },
        )
        Membership.objects.update_or_create(
            user=employee,
            defaults={
                "organization": organization,
                "role": Membership.Role.EMPLOYEE,
                "job_title": "Product designer",
                "annual_allowance": 20,
            },
        )
        Membership.objects.update_or_create(
            user=manager,
            defaults={
                "organization": organization,
                "role": Membership.Role.MANAGER,
                "job_title": "Engineering manager",
                "annual_allowance": 22,
            },
        )
        leave_specs = [
            ("Annual leave", "#5965d8", True),
            ("Sick leave", "#d86767", True),
            ("Personal leave", "#d69b45", True),
            ("Unpaid leave", "#6f7b79", False),
        ]
        leave_types = {}
        for name, color, paid in leave_specs:
            leave_types[name], _ = LeaveType.objects.update_or_create(
                organization=organization,
                name=name,
                defaults={"color": color, "paid": paid},
            )
        today = timezone.localdate()
        LeaveRequest.objects.update_or_create(
            organization=organization,
            requester=employee,
            starts_on=today + timedelta(days=5),
            defaults={
                "leave_type": leave_types["Annual leave"],
                "ends_on": today + timedelta(days=7),
                "reason": "Family event outside the city.",
                "status": LeaveRequest.Status.PENDING,
            },
        )
        LeaveRequest.objects.update_or_create(
            organization=organization,
            requester=employee,
            starts_on=today - timedelta(days=20),
            defaults={
                "leave_type": leave_types["Sick leave"],
                "ends_on": today - timedelta(days=19),
                "reason": "Recovery and rest.",
                "status": LeaveRequest.Status.APPROVED,
                "reviewed_by": owner,
                "reviewed_at": timezone.now(),
            },
        )
        LeaveRequest.objects.update_or_create(
            organization=organization,
            requester=owner,
            starts_on=today + timedelta(days=14),
            defaults={
                "leave_type": leave_types["Personal leave"],
                "ends_on": today + timedelta(days=14),
                "reason": "Personal appointment.",
                "status": LeaveRequest.Status.APPROVED,
                "reviewed_by": manager,
                "reviewed_at": timezone.now(),
            },
        )
        self.stdout.write(self.style.SUCCESS("LeaveLoom demo ready: demo_peopleops / DemoPass123!"))
