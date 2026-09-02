from django.contrib import admin

from .models import (
    ClaimEvent,
    Customer,
    Inspection,
    Membership,
    Organization,
    Product,
    RegisteredItem,
    ReturnClaim,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created_at"]
    search_fields = ["name", "slug"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "organization", "role", "title"]
    list_filter = ["organization", "role"]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "contact_name", "email"]
    list_filter = ["organization"]
    search_fields = ["name", "contact_name", "email"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["sku", "name", "organization", "category", "warranty_months", "active"]
    list_filter = ["organization", "category", "active"]
    search_fields = ["sku", "name"]


@admin.register(RegisteredItem)
class RegisteredItemAdmin(admin.ModelAdmin):
    list_display = ["serial_number", "product", "customer", "purchase_date"]
    list_filter = ["organization", "product"]
    search_fields = ["serial_number", "order_reference", "customer__name"]


class ClaimEventInline(admin.TabularInline):
    model = ClaimEvent
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(ReturnClaim)
class ReturnClaimAdmin(admin.ModelAdmin):
    list_display = [
        "tracking_code",
        "item",
        "organization",
        "priority",
        "status",
        "response_due",
    ]
    list_filter = ["organization", "priority", "status", "issue_category"]
    search_fields = ["tracking_code", "item__serial_number", "item__customer__name"]
    inlines = [ClaimEventInline]


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ["claim", "technician", "condition", "fault_confirmed", "recommendation"]
    list_filter = ["organization", "condition", "fault_confirmed", "recommendation"]


@admin.register(ClaimEvent)
class ClaimEventAdmin(admin.ModelAdmin):
    list_display = ["claim", "status", "actor", "visible_to_customer", "created_at"]
    list_filter = ["organization", "status", "visible_to_customer"]
