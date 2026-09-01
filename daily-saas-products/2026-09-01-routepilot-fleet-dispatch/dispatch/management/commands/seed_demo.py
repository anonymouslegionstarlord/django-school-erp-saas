from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from dispatch.models import (
    Customer,
    DispatchAssignment,
    DriverProfile,
    Membership,
    Organization,
    Shipment,
    ShipmentEvent,
    Vehicle,
)

PASSWORD = "DemoPass123!"


class Command(BaseCommand):
    help = "Create or refresh the RoutePilot demonstration workspace."

    def handle(self, *args, **options):
        organization, _ = Organization.objects.update_or_create(
            slug="northstar-logistics",
            defaults={"name": "Northstar Logistics"},
        )
        users = {}
        user_specs = [
            ("demo_routes", "Maya", "Shah", Membership.Role.OWNER, "Operations owner"),
            (
                "demo_dispatcher",
                "Theo",
                "Morgan",
                Membership.Role.DISPATCHER,
                "Lead dispatcher",
            ),
            ("demo_driver", "Aarav", "Kumar", Membership.Role.DRIVER, "Delivery driver"),
            (
                "demo_driver_two",
                "Nina",
                "Patel",
                Membership.Role.DRIVER,
                "Delivery driver",
            ),
            (
                "demo_route_viewer",
                "Jamie",
                "Lee",
                Membership.Role.VIEWER,
                "Customer operations",
            ),
        ]
        for username, first_name, last_name, role, title in user_specs:
            user, _ = User.objects.get_or_create(username=username)
            user.first_name = first_name
            user.last_name = last_name
            user.email = f"{username}@routepilot.example"
            user.set_password(PASSWORD)
            user.save()
            Membership.objects.update_or_create(
                user=user,
                defaults={"organization": organization, "role": role, "title": title},
            )
            users[username] = user

        today = timezone.localdate()
        driver_one, _ = DriverProfile.objects.update_or_create(
            user=users["demo_driver"],
            defaults={
                "organization": organization,
                "license_number": "DL-RP-22041",
                "license_expiry": today + timedelta(days=540),
                "phone": "+91 98765 41020",
                "status": DriverProfile.Status.ON_ROUTE,
            },
        )
        driver_two, _ = DriverProfile.objects.update_or_create(
            user=users["demo_driver_two"],
            defaults={
                "organization": organization,
                "license_number": "DL-RP-22086",
                "license_expiry": today + timedelta(days=390),
                "phone": "+91 98765 41048",
                "status": DriverProfile.Status.AVAILABLE,
            },
        )

        van, _ = Vehicle.objects.update_or_create(
            organization=organization,
            registration="KA-01-RP-204",
            defaults={
                "name": "Sprinter 204",
                "kind": Vehicle.Kind.VAN,
                "capacity_kg": Decimal("1250.00"),
                "status": Vehicle.Status.ON_ROUTE,
                "odometer_km": 28420,
                "next_service_km": 32000,
            },
        )
        truck, _ = Vehicle.objects.update_or_create(
            organization=organization,
            registration="KA-02-RP-118",
            defaults={
                "name": "Atlas 118",
                "kind": Vehicle.Kind.TRUCK,
                "capacity_kg": Decimal("4200.00"),
                "status": Vehicle.Status.AVAILABLE,
                "odometer_km": 51600,
                "next_service_km": 56000,
            },
        )
        Vehicle.objects.update_or_create(
            organization=organization,
            registration="KA-05-RP-017",
            defaults={
                "name": "Swift 017",
                "kind": Vehicle.Kind.BIKE,
                "capacity_kg": Decimal("35.00"),
                "status": Vehicle.Status.MAINTENANCE,
                "odometer_km": 12280,
                "next_service_km": 12000,
            },
        )

        acme, _ = Customer.objects.update_or_create(
            organization=organization,
            name="Acme Health Labs",
            defaults={
                "contact_name": "Riya Menon",
                "email": "riya@acme-health.example",
                "phone": "+91 80456 71200",
                "notes": "Reception accepts deliveries until 18:30.",
            },
        )
        bluebird, _ = Customer.objects.update_or_create(
            organization=organization,
            name="Bluebird Retail",
            defaults={
                "contact_name": "Kabir Rao",
                "email": "ops@bluebird.example",
                "phone": "+91 80456 71320",
                "notes": "Use loading bay B for pallet deliveries.",
            },
        )
        northwind, _ = Customer.objects.update_or_create(
            organization=organization,
            name="Northwind Kitchens",
            defaults={
                "contact_name": "Anika Das",
                "email": "anika@northwind.example",
                "phone": "+91 80456 71990",
                "notes": "Temperature-sensitive supplies.",
            },
        )

        now = timezone.now()
        active = self._shipment(
            organization,
            "RP-240901-A7K2",
            acme,
            users["demo_dispatcher"],
            pickup="Northstar Hub, Peenya Industrial Area, Bengaluru",
            delivery="Acme Health Labs, Indiranagar, Bengaluru",
            description="Diagnostic supplies · 8 sealed cartons",
            weight="186.50",
            priority=Shipment.Priority.EXPRESS,
            status=Shipment.Status.IN_TRANSIT,
            pickup_at=now - timedelta(hours=2),
            deadline=now + timedelta(hours=2, minutes=40),
        )
        DispatchAssignment.objects.update_or_create(
            shipment=active,
            defaults={
                "organization": organization,
                "driver": driver_one,
                "vehicle": van,
                "assigned_by": users["demo_dispatcher"],
            },
        )
        overdue = self._shipment(
            organization,
            "RP-240901-Q9M4",
            bluebird,
            users["demo_dispatcher"],
            pickup="Bluebird Warehouse, Yeshwanthpur, Bengaluru",
            delivery="Bluebird Store 14, Koramangala, Bengaluru",
            description="Seasonal retail display units",
            weight="760.00",
            priority=Shipment.Priority.URGENT,
            status=Shipment.Status.UNASSIGNED,
            pickup_at=now - timedelta(hours=3),
            deadline=now - timedelta(minutes=35),
        )
        delivered = self._shipment(
            organization,
            "RP-240831-C3N8",
            northwind,
            users["demo_routes"],
            pickup="Cold Chain Hub, Whitefield, Bengaluru",
            delivery="Northwind Kitchens, HSR Layout, Bengaluru",
            description="Refrigerated produce crates",
            weight="520.00",
            priority=Shipment.Priority.STANDARD,
            status=Shipment.Status.DELIVERED,
            pickup_at=now - timedelta(days=1, hours=5),
            deadline=now - timedelta(days=1),
            delivered_at=now - timedelta(days=1, minutes=45),
            delivery_reference="POD-NWK-8831",
            proof_note="Received intact by kitchen manager Anika Das.",
        )
        DispatchAssignment.objects.update_or_create(
            shipment=delivered,
            defaults={
                "organization": organization,
                "driver": driver_two,
                "vehicle": truck,
                "assigned_by": users["demo_routes"],
            },
        )
        planned = self._shipment(
            organization,
            "RP-240901-P5T1",
            bluebird,
            users["demo_dispatcher"],
            pickup="Northstar Hub, Peenya Industrial Area, Bengaluru",
            delivery="Bluebird Store 07, Jayanagar, Bengaluru",
            description="Point-of-sale equipment",
            weight="82.00",
            priority=Shipment.Priority.STANDARD,
            status=Shipment.Status.UNASSIGNED,
            pickup_at=now + timedelta(hours=2),
            deadline=now + timedelta(hours=7),
        )

        ShipmentEvent.objects.filter(shipment__in=[active, overdue, delivered, planned]).delete()
        event_specs = [
            (
                active,
                Shipment.Status.ASSIGNED,
                users["demo_dispatcher"],
                "Assigned to Aarav Kumar in KA-01-RP-204.",
                True,
            ),
            (
                active,
                Shipment.Status.PICKED_UP,
                users["demo_driver"],
                "Eight sealed cartons collected and counted at origin.",
                True,
            ),
            (
                active,
                Shipment.Status.IN_TRANSIT,
                users["demo_driver"],
                "Vehicle departed the hub and is travelling on schedule.",
                True,
            ),
            (
                overdue,
                Shipment.Status.UNASSIGNED,
                users["demo_dispatcher"],
                "Shipment created; urgent capacity is being sourced.",
                True,
            ),
            (
                delivered,
                Shipment.Status.DELIVERED,
                users["demo_driver_two"],
                "Delivered intact to the kitchen receiving desk.",
                True,
            ),
            (
                planned,
                Shipment.Status.UNASSIGNED,
                users["demo_dispatcher"],
                "Shipment is ready for afternoon dispatch.",
                True,
            ),
        ]
        for shipment, status, actor, message, visible in event_specs:
            ShipmentEvent.objects.create(
                organization=organization,
                shipment=shipment,
                actor=actor,
                status=status,
                message=message,
                visible_to_customer=visible,
            )

        self.stdout.write(self.style.SUCCESS("RoutePilot demo workspace is ready."))
        self.stdout.write("Sign in as demo_dispatcher / DemoPass123!")

    def _shipment(
        self,
        organization,
        tracking_code,
        customer,
        creator,
        *,
        pickup,
        delivery,
        description,
        weight,
        priority,
        status,
        pickup_at,
        deadline,
        delivered_at=None,
        delivery_reference="",
        proof_note="",
    ):
        shipment, _ = Shipment.objects.update_or_create(
            organization=organization,
            tracking_code=tracking_code,
            defaults={
                "customer": customer,
                "pickup_address": pickup,
                "delivery_address": delivery,
                "package_description": description,
                "weight_kg": Decimal(weight),
                "priority": priority,
                "status": status,
                "scheduled_pickup": pickup_at,
                "delivery_deadline": deadline,
                "delivered_at": delivered_at,
                "delivery_reference": delivery_reference,
                "proof_note": proof_note,
                "failure_reason": "",
                "created_by": creator,
            },
        )
        return shipment
