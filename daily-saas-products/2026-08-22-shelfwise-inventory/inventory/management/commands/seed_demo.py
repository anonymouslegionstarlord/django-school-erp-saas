from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import (
    Membership,
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Supplier,
)


class Command(BaseCommand):
    help = "Create or refresh a local ShelfWise demonstration workspace."

    def handle(self, *args, **options):
        user, _ = User.objects.get_or_create(
            username="demo_inventory",
            defaults={"email": "demo@shelfwise.local", "first_name": "Aarav"},
        )
        user.set_password("DemoPass123!")
        user.save()
        organization, _ = Organization.objects.get_or_create(
            slug="riverbend-supplies", defaults={"name": "Riverbend Supplies"}
        )
        Membership.objects.update_or_create(
            user=user,
            defaults={"organization": organization, "role": Membership.Role.OWNER},
        )
        atlas, _ = Supplier.objects.update_or_create(
            organization=organization,
            email="orders@atlas.example",
            defaults={
                "name": "Atlas Wholesale",
                "phone": "+91 98765 02001",
                "lead_time_days": 5,
            },
        )
        nova, _ = Supplier.objects.update_or_create(
            organization=organization,
            email="supply@nova.example",
            defaults={"name": "Nova Packaging", "lead_time_days": 8},
        )
        specs = [
            ("OF-100", "A4 recycled paper", "Office", atlas, "240.00", "349.00", 12, 28),
            ("PK-210", "Kraft shipping box", "Packaging", nova, "32.00", "55.00", 20, 9),
            ("OF-330", "Permanent marker set", "Office", atlas, "85.00", "129.00", 8, 14),
            ("PK-410", "Paper packing tape", "Packaging", nova, "48.00", "75.00", 10, 6),
        ]
        products = {}
        for sku, name, category, supplier, cost, price, reorder, opening in specs:
            product, created = Product.objects.update_or_create(
                organization=organization,
                sku=sku,
                defaults={
                    "name": name,
                    "category": category,
                    "supplier": supplier,
                    "unit_cost": Decimal(cost),
                    "sale_price": Decimal(price),
                    "reorder_level": reorder,
                    "active": True,
                },
            )
            products[sku] = product
            if created or not product.movements.exists():
                StockMovement.objects.create(
                    organization=organization,
                    product=product,
                    kind=StockMovement.Kind.RECEIPT,
                    quantity=opening,
                    reference="OPENING",
                    created_by=user,
                )
        order, _ = PurchaseOrder.objects.update_or_create(
            organization=organization,
            number="PO-2026-001",
            defaults={
                "supplier": nova,
                "status": PurchaseOrder.Status.ORDERED,
                "expected_on": timezone.localdate() + timedelta(days=5),
                "notes": "Replenishment for products below their reorder point.",
            },
        )
        PurchaseOrderItem.objects.update_or_create(
            purchase_order=order,
            product=products["PK-210"],
            defaults={"quantity": 40, "unit_cost": Decimal("31.00")},
        )
        PurchaseOrderItem.objects.update_or_create(
            purchase_order=order,
            product=products["PK-410"],
            defaults={"quantity": 24, "unit_cost": Decimal("46.00")},
        )
        self.stdout.write(self.style.SUCCESS("ShelfWise demo ready: demo_inventory / DemoPass123!"))
