from django.contrib import admin

from .models import (
    Membership,
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Supplier,
)

admin.site.register(
    [Organization, Membership, Supplier, Product, StockMovement, PurchaseOrder, PurchaseOrderItem]
)
