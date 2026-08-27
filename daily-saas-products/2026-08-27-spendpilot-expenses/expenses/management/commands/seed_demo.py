from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from expenses.models import (
    Activity,
    CostCenter,
    ExpenseCategory,
    ExpenseItem,
    ExpenseReport,
    Membership,
    Organization,
)


class Command(BaseCommand):
    help = "Create or refresh the local SpendPilot demonstration workspace."

    @transaction.atomic
    def handle(self, *args, **options):
        organization, _ = Organization.objects.update_or_create(
            slug="northstar-studio",
            defaults={"name": "Northstar Studio", "base_currency": "INR"},
        )
        users = {}
        user_specs = [
            ("demo_spend", "Aarav", "Mehta", Membership.Role.OWNER),
            ("demo_manager", "Maya", "Kapoor", Membership.Role.MANAGER),
            ("demo_employee", "Neha", "Singh", Membership.Role.EMPLOYEE),
            ("demo_finance", "Rohan", "Iyer", Membership.Role.FINANCE),
        ]
        for username, first_name, last_name, role in user_specs:
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_staff": role == Membership.Role.OWNER,
                },
            )
            user.set_password("DemoPass123!")
            user.save(update_fields=["password"])
            Membership.objects.update_or_create(
                user=user, defaults={"organization": organization, "role": role}
            )
            users[role] = user

        cost_centers = {}
        for code, name, manager_role in [
            ("PRODUCT", "Product & engineering", Membership.Role.MANAGER),
            ("SALES", "Sales & customer success", Membership.Role.MANAGER),
            ("OPS", "Business operations", Membership.Role.OWNER),
        ]:
            cost_center, _ = CostCenter.objects.update_or_create(
                organization=organization,
                code=code,
                defaults={"name": name, "manager": users[manager_role], "active": True},
            )
            cost_centers[code] = cost_center

        categories = {}
        for name, daily_limit, receipt_threshold in [
            ("Travel", "15000.00", "500.00"),
            ("Meals", "2500.00", "500.00"),
            ("Software", "0.00", "1.00"),
            ("Office", "5000.00", "500.00"),
        ]:
            category, _ = ExpenseCategory.objects.update_or_create(
                organization=organization,
                name=name,
                defaults={
                    "daily_limit": Decimal(daily_limit),
                    "receipt_required_over": Decimal(receipt_threshold),
                    "active": True,
                },
            )
            categories[name] = category

        today = timezone.localdate()
        now = timezone.now()
        reports = [
            {
                "title": "Client workshop · Bengaluru",
                "purpose": "On-site discovery workshop for the Atlas account.",
                "cost_center": cost_centers["SALES"],
                "status": ExpenseReport.Status.SUBMITTED,
                "trip_start": today - timedelta(days=10),
                "trip_end": today - timedelta(days=8),
                "submitted_at": now - timedelta(days=7),
                "items": [
                    (
                        "Travel",
                        today - timedelta(days=10),
                        "IndiGo",
                        "Return flight to Bengaluru",
                        "12800.00",
                        "https://example.com/receipts/flight-1042",
                    ),
                    (
                        "Meals",
                        today - timedelta(days=9),
                        "The Local Table",
                        "Client dinner for four",
                        "3100.00",
                        "",
                    ),
                ],
            },
            {
                "title": "Design software renewal",
                "purpose": "Annual interface design tooling for the product team.",
                "cost_center": cost_centers["PRODUCT"],
                "status": ExpenseReport.Status.APPROVED,
                "submitted_at": now - timedelta(days=6),
                "reviewed_by": users[Membership.Role.MANAGER],
                "decided_at": now - timedelta(days=5),
                "decision_note": "Approved against the product tooling budget.",
                "items": [
                    (
                        "Software",
                        today - timedelta(days=7),
                        "Figma",
                        "Annual professional plan",
                        "9999.00",
                        "https://example.com/receipts/figma-2026",
                    )
                ],
            },
            {
                "title": "Quarterly team meetup",
                "purpose": "Team planning lunch following the quarterly review.",
                "cost_center": cost_centers["OPS"],
                "status": ExpenseReport.Status.REIMBURSED,
                "submitted_at": now - timedelta(days=14),
                "reviewed_by": users[Membership.Role.MANAGER],
                "decided_at": now - timedelta(days=13),
                "reimbursed_at": now - timedelta(days=11),
                "decision_note": "Within the approved team-events allocation.",
                "items": [
                    (
                        "Meals",
                        today - timedelta(days=15),
                        "Green House Cafe",
                        "Planning lunch",
                        "2180.00",
                        "https://example.com/receipts/team-lunch",
                    )
                ],
            },
            {
                "title": "Home-office accessories",
                "purpose": "Ergonomic keyboard and laptop stand for remote work.",
                "cost_center": cost_centers["PRODUCT"],
                "status": ExpenseReport.Status.DRAFT,
                "items": [
                    (
                        "Office",
                        today - timedelta(days=1),
                        "WorkWell",
                        "Keyboard and stand",
                        "4200.00",
                        "https://example.com/receipts/workwell",
                    )
                ],
            },
        ]

        for spec in reports:
            items = spec.pop("items")
            report, _ = ExpenseReport.objects.update_or_create(
                organization=organization,
                title=spec["title"],
                defaults={
                    "submitter": users[Membership.Role.EMPLOYEE],
                    "purpose": spec["purpose"],
                    "cost_center": spec["cost_center"],
                    "status": spec["status"],
                    "trip_start": spec.get("trip_start"),
                    "trip_end": spec.get("trip_end"),
                    "submitted_at": spec.get("submitted_at"),
                    "reviewed_by": spec.get("reviewed_by"),
                    "decided_at": spec.get("decided_at"),
                    "reimbursed_at": spec.get("reimbursed_at"),
                    "decision_note": spec.get("decision_note", ""),
                },
            )
            report.items.all().delete()
            report.activities.all().delete()
            for category_name, expense_date, merchant, description, amount, receipt_url in items:
                item = ExpenseItem(
                    organization=organization,
                    report=report,
                    category=categories[category_name],
                    expense_date=expense_date,
                    merchant=merchant,
                    description=description,
                    amount=Decimal(amount),
                    receipt_url=receipt_url,
                )
                item.full_clean()
                item.save()
            Activity.objects.create(
                organization=organization,
                report=report,
                actor=users[Membership.Role.EMPLOYEE],
                action=Activity.Action.CREATED,
                message="Demo report created",
            )
            if report.submitted_at:
                Activity.objects.create(
                    organization=organization,
                    report=report,
                    actor=users[Membership.Role.EMPLOYEE],
                    action=Activity.Action.SUBMITTED,
                    message="Submitted for manager review",
                )
            if report.decided_at:
                Activity.objects.create(
                    organization=organization,
                    report=report,
                    actor=users[Membership.Role.MANAGER],
                    action=(
                        Activity.Action.APPROVED
                        if report.status
                        in [ExpenseReport.Status.APPROVED, ExpenseReport.Status.REIMBURSED]
                        else Activity.Action.REJECTED
                    ),
                    message="Manager decision recorded",
                )
            if report.reimbursed_at:
                Activity.objects.create(
                    organization=organization,
                    report=report,
                    actor=users[Membership.Role.FINANCE],
                    action=Activity.Action.REIMBURSED,
                    message="Reimbursement recorded by finance",
                )

        self.stdout.write(
            self.style.SUCCESS(
                "SpendPilot demo ready: demo_spend / demo_manager / demo_employee / "
                "demo_finance (password: DemoPass123!)"
            )
        )
