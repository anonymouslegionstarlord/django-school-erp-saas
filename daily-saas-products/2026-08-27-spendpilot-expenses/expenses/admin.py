from django.contrib import admin

from .models import (
    Activity,
    CostCenter,
    ExpenseCategory,
    ExpenseItem,
    ExpenseReport,
    Membership,
    Organization,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "base_currency", "created_at"]
    search_fields = ["name", "slug"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "organization", "role"]
    list_filter = ["role", "organization"]


@admin.register(ExpenseReport)
class ExpenseReportAdmin(admin.ModelAdmin):
    list_display = ["reference", "title", "organization", "submitter", "status", "updated_at"]
    list_filter = ["status", "organization"]
    search_fields = ["title", "submitter__username"]


@admin.register(ExpenseItem)
class ExpenseItemAdmin(admin.ModelAdmin):
    list_display = ["merchant", "report", "category", "amount", "expense_date"]
    list_filter = ["organization", "category"]


admin.site.register([CostCenter, ExpenseCategory, Activity])
