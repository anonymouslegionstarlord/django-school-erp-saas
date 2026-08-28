from django.contrib import admin

from .models import (
    Activity,
    Membership,
    Organization,
    Product,
    TestCase,
    TestExecution,
    TestRun,
    TestSuite,
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["key", "name", "organization", "owner", "status"]
    list_filter = ["status", "organization"]
    search_fields = ["key", "name"]


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ["case_key", "title", "suite", "priority", "status"]
    list_filter = ["organization", "priority", "test_type", "status"]
    search_fields = ["case_key", "title", "requirement_reference"]


@admin.register(TestRun)
class TestRunAdmin(admin.ModelAdmin):
    list_display = ["reference", "name", "product", "target_version", "status"]
    list_filter = ["organization", "environment", "status"]


admin.site.register([Organization, Membership, TestSuite, TestExecution, Activity])
