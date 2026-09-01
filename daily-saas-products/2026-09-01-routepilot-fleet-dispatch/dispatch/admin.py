from django.contrib import admin

from .models import (
    Customer,
    DispatchAssignment,
    DriverProfile,
    Membership,
    Organization,
    Shipment,
    ShipmentEvent,
    Vehicle,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created_at"]
    search_fields = ["name", "slug"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "organization", "role", "title"]
    list_filter = ["role", "organization"]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "contact_name", "email"]
    search_fields = ["name", "contact_name", "email"]
    list_filter = ["organization"]


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "organization", "license_number", "license_expiry", "status"]
    list_filter = ["organization", "status"]


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ["registration", "name", "organization", "kind", "capacity_kg", "status"]
    list_filter = ["organization", "kind", "status"]
    search_fields = ["registration", "name"]


class ShipmentEventInline(admin.TabularInline):
    model = ShipmentEvent
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = [
        "tracking_code",
        "customer",
        "organization",
        "priority",
        "status",
        "delivery_deadline",
    ]
    list_filter = ["organization", "priority", "status"]
    search_fields = ["tracking_code", "customer__name"]
    inlines = [ShipmentEventInline]


@admin.register(DispatchAssignment)
class DispatchAssignmentAdmin(admin.ModelAdmin):
    list_display = ["shipment", "driver", "vehicle", "assigned_by", "assigned_at"]
    list_filter = ["organization"]


@admin.register(ShipmentEvent)
class ShipmentEventAdmin(admin.ModelAdmin):
    list_display = ["shipment", "status", "actor", "visible_to_customer", "created_at"]
    list_filter = ["organization", "status", "visible_to_customer"]
