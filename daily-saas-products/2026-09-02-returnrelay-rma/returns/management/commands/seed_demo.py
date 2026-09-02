from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from returns.models import (
    ClaimEvent,
    Customer,
    Inspection,
    Membership,
    Organization,
    Product,
    RegisteredItem,
    ReturnClaim,
)

PASSWORD = "DemoPass123!"


class Command(BaseCommand):
    help = "Create or refresh the ReturnRelay demonstration workspace."

    def handle(self, *args, **options):
        organization, _ = Organization.objects.update_or_create(
            slug="summit-appliances",
            defaults={"name": "Summit Appliances"},
        )
        users = {}
        user_specs = [
            ("demo_returns", "Maya", "Shah", Membership.Role.OWNER, "Operations owner"),
            (
                "demo_claims",
                "Theo",
                "Morgan",
                Membership.Role.CLAIMS_MANAGER,
                "Claims manager",
            ),
            (
                "demo_technician",
                "Aarav",
                "Kumar",
                Membership.Role.TECHNICIAN,
                "Warranty technician",
            ),
            (
                "demo_returns_viewer",
                "Jamie",
                "Lee",
                Membership.Role.VIEWER,
                "Customer experience analyst",
            ),
        ]
        for username, first_name, last_name, role, title in user_specs:
            user, _ = User.objects.get_or_create(username=username)
            user.first_name = first_name
            user.last_name = last_name
            user.email = f"{username}@returnrelay.example"
            user.set_password(PASSWORD)
            user.save()
            Membership.objects.update_or_create(
                user=user,
                defaults={"organization": organization, "role": role, "title": title},
            )
            users[username] = user

        customers = {
            "greenleaf": self._customer(
                organization,
                "Greenleaf Coworking",
                "Riya Menon",
                "riya@greenleaf.example",
                "+91 80456 71200",
            ),
            "bluebird": self._customer(
                organization,
                "Bluebird Café",
                "Kabir Rao",
                "kabir@bluebird.example",
                "+91 80456 71320",
            ),
            "northwind": self._customer(
                organization,
                "Northwind Design Studio",
                "Anika Das",
                "anika@northwind.example",
                "+91 80456 71990",
            ),
        }
        products = {
            "coffee": self._product(
                organization,
                "SA-COF-220",
                "AeroBrew Coffee Station",
                Product.Category.APPLIANCE,
                "18990.00",
                24,
            ),
            "purifier": self._product(
                organization,
                "SA-AIR-105",
                "AirPure Mini",
                Product.Category.APPLIANCE,
                "12450.00",
                12,
            ),
            "desk": self._product(
                organization,
                "SA-DSK-430",
                "ErgoDesk Flex",
                Product.Category.FURNITURE,
                "32990.00",
                36,
            ),
        }
        today = timezone.localdate()
        items = {
            "coffee": self._item(
                organization,
                products["coffee"],
                customers["bluebird"],
                "AB220-24-00817",
                "ORD-240218-8472",
                today - timedelta(days=196),
            ),
            "purifier": self._item(
                organization,
                products["purifier"],
                customers["greenleaf"],
                "AP105-24-01442",
                "ORD-240711-2209",
                today - timedelta(days=418),
            ),
            "desk": self._item(
                organization,
                products["desk"],
                customers["northwind"],
                "ED430-25-00311",
                "ORD-250903-5130",
                today - timedelta(days=364),
            ),
        }

        now = timezone.now()
        claims = [
            self._claim(
                organization,
                "RMA-260902-A7K2F1C8",
                items["coffee"],
                users["demo_claims"],
                issue=ReturnClaim.IssueCategory.PERFORMANCE,
                description="The boiler loses pressure after the second drink and displays E-14.",
                remedy=ReturnClaim.Remedy.REPAIR,
                priority=ReturnClaim.Priority.URGENT,
                status=ReturnClaim.Status.TRIAGE,
                response_due=now - timedelta(minutes=42),
            ),
            self._claim(
                organization,
                "RMA-260902-Q9M4D3E7",
                items["desk"],
                users["demo_returns"],
                issue=ReturnClaim.IssueCategory.DEFECTIVE,
                description="The left lifting column stops ten centimetres below the saved height.",
                remedy=ReturnClaim.Remedy.REPLACEMENT,
                priority=ReturnClaim.Priority.HIGH,
                status=ReturnClaim.Status.AWAITING_ITEM,
                response_due=now + timedelta(hours=8),
                approved_at=now - timedelta(hours=2),
            ),
            self._claim(
                organization,
                "RMA-260901-C3N8B5T2",
                items["coffee"],
                users["demo_claims"],
                issue=ReturnClaim.IssueCategory.DAMAGED,
                description="The machine arrived with a dented side panel and leaking reservoir.",
                remedy=ReturnClaim.Remedy.REPLACEMENT,
                priority=ReturnClaim.Priority.NORMAL,
                status=ReturnClaim.Status.RECEIVED,
                response_due=now + timedelta(hours=19),
                approved_at=now - timedelta(days=1),
            ),
            self._claim(
                organization,
                "RMA-260831-P5T1H6R4",
                items["desk"],
                users["demo_returns"],
                issue=ReturnClaim.IssueCategory.DEFECTIVE,
                description="Control panel intermittently resets while changing height.",
                remedy=ReturnClaim.Remedy.REPAIR,
                priority=ReturnClaim.Priority.NORMAL,
                status=ReturnClaim.Status.INSPECTING,
                response_due=now + timedelta(hours=27),
                approved_at=now - timedelta(days=2),
            ),
            self._claim(
                organization,
                "RMA-260827-L2W7J9S5",
                items["purifier"],
                users["demo_claims"],
                issue=ReturnClaim.IssueCategory.PERFORMANCE,
                description="Airflow is lower than expected after filter replacement.",
                remedy=ReturnClaim.Remedy.REFUND,
                priority=ReturnClaim.Priority.LOW,
                status=ReturnClaim.Status.REJECTED,
                response_due=now - timedelta(days=4),
                rejected_at=now - timedelta(days=3),
                rejection_reason="The registered warranty expired before the reported fault.",
            ),
            self._claim(
                organization,
                "RMA-260824-V4X6K1D9",
                items["coffee"],
                users["demo_returns"],
                issue=ReturnClaim.IssueCategory.DEFECTIVE,
                description="Temperature sensor produced inconsistent readings during service.",
                remedy=ReturnClaim.Remedy.REPAIR,
                priority=ReturnClaim.Priority.NORMAL,
                status=ReturnClaim.Status.RESOLVED,
                response_due=now - timedelta(days=6),
                approved_at=now - timedelta(days=8),
                resolved_at=now - timedelta(days=1),
                resolution=ReturnClaim.Resolution.REPAIRED,
                resolution_summary="Replaced the temperature sensor and passed a 20-cycle test.",
            ),
        ]

        inspecting = claims[3]
        Inspection.objects.update_or_create(
            claim=inspecting,
            defaults={
                "organization": organization,
                "technician": users["demo_technician"],
                "condition": Inspection.Condition.USED,
                "fault_confirmed": True,
                "findings": "A loose control-cable connector reproduces the intermittent reset.",
                "recommendation": Inspection.Recommendation.REPAIR,
            },
        )
        resolved = claims[5]
        Inspection.objects.update_or_create(
            claim=resolved,
            defaults={
                "organization": organization,
                "technician": users["demo_technician"],
                "condition": Inspection.Condition.USED,
                "fault_confirmed": True,
                "findings": "Sensor resistance moved outside tolerance under sustained heat.",
                "recommendation": Inspection.Recommendation.REPAIR,
            },
        )
        Inspection.objects.filter(claim__in=claims).exclude(
            claim__in=[inspecting, resolved]
        ).delete()

        ClaimEvent.objects.filter(claim__in=claims).delete()
        event_specs = [
            (
                claims[0],
                users["demo_claims"],
                ReturnClaim.Status.SUBMITTED,
                "Claim received from Bluebird Café.",
                True,
            ),
            (
                claims[0],
                users["demo_claims"],
                ReturnClaim.Status.TRIAGE,
                "Warranty and reported symptoms are under review.",
                True,
            ),
            (
                claims[1],
                users["demo_returns"],
                ReturnClaim.Status.APPROVED,
                "Coverage confirmed; return instructions were issued.",
                True,
            ),
            (
                claims[1],
                users["demo_claims"],
                ReturnClaim.Status.AWAITING_ITEM,
                "Waiting for the desk controller to reach our service center.",
                True,
            ),
            (
                claims[2],
                users["demo_claims"],
                ReturnClaim.Status.RECEIVED,
                "The coffee station arrived and passed intake checks.",
                True,
            ),
            (
                claims[3],
                users["demo_technician"],
                ReturnClaim.Status.INSPECTING,
                "Inspection confirmed a repairable connector fault.",
                True,
            ),
            (
                claims[3],
                users["demo_technician"],
                ReturnClaim.Status.INSPECTING,
                "Internal: reserve replacement harness SA-HRN-42.",
                False,
            ),
            (
                claims[4],
                users["demo_claims"],
                ReturnClaim.Status.REJECTED,
                "The claim is outside the registered warranty period.",
                True,
            ),
            (
                claims[5],
                users["demo_technician"],
                ReturnClaim.Status.INSPECTING,
                "The temperature sensor fault was confirmed.",
                True,
            ),
            (
                claims[5],
                users["demo_claims"],
                ReturnClaim.Status.RESOLVED,
                "Repair completed and the unit passed final testing.",
                True,
            ),
        ]
        for claim, actor, status, message, visible in event_specs:
            ClaimEvent.objects.create(
                organization=organization,
                claim=claim,
                actor=actor,
                status=status,
                message=message,
                visible_to_customer=visible,
            )

        self.stdout.write(self.style.SUCCESS("ReturnRelay demo workspace is ready."))
        self.stdout.write("Sign in as demo_claims / DemoPass123!")

    def _customer(self, organization, name, contact_name, email, phone):
        customer, _ = Customer.objects.update_or_create(
            organization=organization,
            name=name,
            defaults={"contact_name": contact_name, "email": email, "phone": phone},
        )
        return customer

    def _product(self, organization, sku, name, category, price, warranty_months):
        product, _ = Product.objects.update_or_create(
            organization=organization,
            sku=sku,
            defaults={
                "name": name,
                "category": category,
                "retail_price": Decimal(price),
                "warranty_months": warranty_months,
                "active": True,
            },
        )
        return product

    def _item(self, organization, product, customer, serial, order, purchase_date):
        item, _ = RegisteredItem.objects.update_or_create(
            organization=organization,
            serial_number=serial,
            defaults={
                "product": product,
                "customer": customer,
                "order_reference": order,
                "purchase_date": purchase_date,
            },
        )
        return item

    def _claim(
        self,
        organization,
        tracking_code,
        item,
        creator,
        *,
        issue,
        description,
        remedy,
        priority,
        status,
        response_due,
        approved_at=None,
        rejected_at=None,
        rejection_reason="",
        resolved_at=None,
        resolution="",
        resolution_summary="",
    ):
        claim, _ = ReturnClaim.objects.update_or_create(
            organization=organization,
            tracking_code=tracking_code,
            defaults={
                "item": item,
                "issue_category": issue,
                "description": description,
                "requested_remedy": remedy,
                "priority": priority,
                "status": status,
                "response_due": response_due,
                "approved_at": approved_at,
                "rejected_at": rejected_at,
                "rejection_reason": rejection_reason,
                "resolution": resolution,
                "resolution_summary": resolution_summary,
                "resolution_amount": Decimal("0.00"),
                "resolved_at": resolved_at,
                "created_by": creator,
            },
        )
        return claim
