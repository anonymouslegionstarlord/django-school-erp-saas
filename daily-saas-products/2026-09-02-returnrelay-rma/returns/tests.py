import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import CustomerForm, ProductForm, RegisteredItemForm, SignupForm, TeamMemberForm
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
from .services import (
    generate_tracking_code,
    record_inspection,
    sla_deadline,
    transition_choices,
    transition_claim,
)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ReturnRelayTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Summit", slug="summit")
        self.other_organization = Organization.objects.create(name="Other", slug="other")
        self.owner = self.make_user("owner", Membership.Role.OWNER)
        self.manager = self.make_user("manager", Membership.Role.CLAIMS_MANAGER)
        self.technician = self.make_user("technician", Membership.Role.TECHNICIAN)
        self.viewer = self.make_user("viewer", Membership.Role.VIEWER)
        self.other_user = self.make_user(
            "other-owner", Membership.Role.OWNER, self.other_organization
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            name="Acme Café",
            contact_name="Alex Morgan",
            email="alex@example.com",
            phone="555-0100",
        )
        self.product = Product.objects.create(
            organization=self.organization,
            sku="COF-100",
            name="Coffee Station",
            category=Product.Category.APPLIANCE,
            retail_price=Decimal("12000.00"),
            warranty_months=24,
        )
        self.item = RegisteredItem.objects.create(
            organization=self.organization,
            product=self.product,
            customer=self.customer,
            serial_number="SERIAL-100",
            order_reference="ORDER-100",
            purchase_date=timezone.localdate() - timedelta(days=90),
        )
        self.claim = ReturnClaim.objects.create(
            organization=self.organization,
            tracking_code="RMA-TEST-100",
            item=self.item,
            issue_category=ReturnClaim.IssueCategory.DEFECTIVE,
            description="The heating element stops after one cycle.",
            requested_remedy=ReturnClaim.Remedy.REPAIR,
            priority=ReturnClaim.Priority.HIGH,
            response_due=timezone.now() + timedelta(hours=8),
            created_by=self.owner,
        )

    def make_user(self, username, role, organization=None):
        user = User.objects.create_user(username=username, password="StrongPass123!")
        Membership.objects.create(
            user=user,
            organization=organization or self.organization,
            role=role,
            title=role.replace("_", " ").title(),
        )
        return user

    def move_to_received(self):
        for status in [
            ReturnClaim.Status.TRIAGE,
            ReturnClaim.Status.APPROVED,
            ReturnClaim.Status.AWAITING_ITEM,
            ReturnClaim.Status.RECEIVED,
        ]:
            self.claim = transition_claim(
                claim=self.claim,
                target_status=status,
                actor=self.manager,
            )
        return self.claim

    def add_inspection(self, claim=None, actor=None):
        return record_inspection(
            claim=claim or self.claim,
            actor=actor or self.technician,
            condition=Inspection.Condition.USED,
            fault_confirmed=True,
            findings="Loose connector reproduced the reported issue.",
            recommendation=Inspection.Recommendation.REPAIR,
            customer_update="The fault has been confirmed.",
        )


class ModelTests(ReturnRelayTestCase):
    def test_membership_permissions_follow_role(self):
        self.assertTrue(self.owner.returnrelay_membership.can_manage)
        self.assertTrue(self.manager.returnrelay_membership.can_inspect)
        self.assertTrue(self.technician.returnrelay_membership.can_inspect)
        self.assertFalse(self.technician.returnrelay_membership.can_manage)
        self.assertFalse(self.viewer.returnrelay_membership.can_inspect)

    def test_warranty_expiry_handles_end_of_month(self):
        self.item.purchase_date = date(2024, 2, 29)
        self.product.warranty_months = 12
        self.assertEqual(self.item.warranty_expires, date(2025, 2, 28))

    def test_warranty_eligibility_is_date_aware(self):
        self.assertTrue(self.item.is_in_warranty)
        self.item.purchase_date = timezone.localdate() - timedelta(days=900)
        self.assertFalse(self.item.is_in_warranty)

    def test_registered_item_rejects_future_purchase(self):
        self.item.purchase_date = timezone.localdate() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            self.item.full_clean()

    def test_registered_item_rejects_cross_tenant_product(self):
        other_product = Product.objects.create(
            organization=self.other_organization,
            sku="OTHER",
            name="Other",
            category=Product.Category.OTHER,
            retail_price=1,
        )
        self.item.product = other_product
        with self.assertRaises(ValidationError):
            self.item.full_clean()

    def test_registered_item_rejects_cross_tenant_customer(self):
        other_customer = Customer.objects.create(
            organization=self.other_organization,
            name="Other customer",
            contact_name="Other",
            email="other@example.com",
            phone="555",
        )
        self.item.customer = other_customer
        with self.assertRaises(ValidationError):
            self.item.full_clean()

    def test_claim_rejects_cross_tenant_item(self):
        other_customer = Customer.objects.create(
            organization=self.other_organization,
            name="Tenant two",
            contact_name="Other",
            email="tenant2@example.com",
            phone="555",
        )
        other_product = Product.objects.create(
            organization=self.other_organization,
            sku="TENANT-2",
            name="Other product",
            category=Product.Category.OTHER,
            retail_price=1,
        )
        other_item = RegisteredItem.objects.create(
            organization=self.other_organization,
            product=other_product,
            customer=other_customer,
            serial_number="OTHER-SERIAL",
            order_reference="OTHER-ORDER",
            purchase_date=timezone.localdate(),
        )
        self.claim.item = other_item
        with self.assertRaises(ValidationError):
            self.claim.full_clean()

    def test_claim_rejects_cross_tenant_creator(self):
        self.claim.created_by = self.other_user
        with self.assertRaises(ValidationError):
            self.claim.full_clean()

    def test_rejected_claim_requires_reason_and_timestamp(self):
        self.claim.status = ReturnClaim.Status.REJECTED
        with self.assertRaises(ValidationError) as context:
            self.claim.full_clean()
        self.assertIn("rejection_reason", context.exception.message_dict)
        self.assertIn("rejected_at", context.exception.message_dict)

    def test_resolved_refund_requires_positive_amount(self):
        self.claim.status = ReturnClaim.Status.RESOLVED
        self.claim.resolved_at = timezone.now()
        self.claim.resolution = ReturnClaim.Resolution.REFUNDED
        self.claim.resolution_summary = "Approved refund."
        with self.assertRaises(ValidationError):
            self.claim.full_clean()

    def test_resolved_replacement_requires_reference(self):
        self.claim.status = ReturnClaim.Status.RESOLVED
        self.claim.resolved_at = timezone.now()
        self.claim.resolution = ReturnClaim.Resolution.REPLACED
        self.claim.resolution_summary = "Replacement approved."
        with self.assertRaises(ValidationError):
            self.claim.full_clean()

    def test_closed_claim_requires_closed_timestamp(self):
        self.claim.status = ReturnClaim.Status.CLOSED
        self.claim.resolved_at = timezone.now()
        self.claim.resolution = ReturnClaim.Resolution.REPAIRED
        self.claim.resolution_summary = "Repaired."
        with self.assertRaises(ValidationError):
            self.claim.full_clean()

    def test_open_and_overdue_properties_exclude_terminal_states(self):
        self.claim.response_due = timezone.now() - timedelta(minutes=1)
        self.assertTrue(self.claim.is_open)
        self.assertTrue(self.claim.is_overdue)
        self.claim.status = ReturnClaim.Status.RESOLVED
        self.assertFalse(self.claim.is_overdue)
        self.claim.status = ReturnClaim.Status.CLOSED
        self.assertFalse(self.claim.is_open)

    def test_inspection_rejects_non_inspector(self):
        inspection = Inspection(
            organization=self.organization,
            claim=self.claim,
            technician=self.viewer,
            condition=Inspection.Condition.USED,
            findings="Test",
            recommendation=Inspection.Recommendation.NO_FAULT,
        )
        with self.assertRaises(ValidationError):
            inspection.full_clean()

    def test_inspection_rejects_cross_tenant_claim(self):
        inspection = Inspection(
            organization=self.other_organization,
            claim=self.claim,
            technician=self.other_user,
            condition=Inspection.Condition.USED,
            findings="Test",
            recommendation=Inspection.Recommendation.NO_FAULT,
        )
        with self.assertRaises(ValidationError):
            inspection.full_clean()

    def test_event_rejects_cross_tenant_actor(self):
        event = ClaimEvent(
            organization=self.organization,
            claim=self.claim,
            actor=self.other_user,
            status=self.claim.status,
            message="Invalid actor",
        )
        with self.assertRaises(ValidationError):
            event.full_clean()

    def test_event_rejects_cross_tenant_claim(self):
        event = ClaimEvent(
            organization=self.other_organization,
            claim=self.claim,
            actor=self.other_user,
            status=self.claim.status,
            message="Invalid claim",
        )
        with self.assertRaises(ValidationError):
            event.full_clean()


class ServiceTests(ReturnRelayTestCase):
    def test_sla_deadline_uses_priority_hours(self):
        start = timezone.now()
        self.assertEqual(
            sla_deadline(ReturnClaim.Priority.URGENT, start), start + timedelta(hours=4)
        )
        self.assertEqual(sla_deadline(ReturnClaim.Priority.LOW, start), start + timedelta(hours=72))

    def test_tracking_code_is_prefixed_and_unique(self):
        first = generate_tracking_code(self.organization)
        second = generate_tracking_code(self.organization)
        self.assertTrue(first.startswith("RMA-"))
        self.assertNotEqual(first, second)

    def test_transition_choices_are_role_and_state_aware(self):
        manager_choices = transition_choices(self.claim, self.manager.returnrelay_membership)
        self.assertEqual(manager_choices[0][0], ReturnClaim.Status.TRIAGE)
        self.assertEqual(transition_choices(self.claim, self.viewer.returnrelay_membership), [])

    def test_only_managers_can_transition(self):
        with self.assertRaises(PermissionDenied):
            transition_claim(
                claim=self.claim,
                target_status=ReturnClaim.Status.TRIAGE,
                actor=self.technician,
            )

    def test_unknown_and_illegal_transitions_are_rejected(self):
        with self.assertRaises(ValidationError):
            transition_claim(claim=self.claim, target_status="unknown", actor=self.manager)
        with self.assertRaises(ValidationError):
            transition_claim(
                claim=self.claim,
                target_status=ReturnClaim.Status.RESOLVED,
                actor=self.manager,
            )

    def test_happy_path_reaches_received_with_audit_events(self):
        self.move_to_received()
        self.assertEqual(self.claim.status, ReturnClaim.Status.RECEIVED)
        self.assertEqual(self.claim.events.count(), 4)
        self.assertIsNotNone(self.claim.approved_at)

    def test_transition_uses_custom_visibility_and_default_message(self):
        transitioned = transition_claim(
            claim=self.claim,
            target_status=ReturnClaim.Status.TRIAGE,
            actor=self.manager,
            visible_to_customer=False,
        )
        event = transitioned.events.get()
        self.assertFalse(event.visible_to_customer)
        self.assertIn("in triage", event.message)

    def test_rejection_requires_reason(self):
        self.claim.status = ReturnClaim.Status.TRIAGE
        self.claim.save()
        with self.assertRaises(ValidationError):
            transition_claim(
                claim=self.claim,
                target_status=ReturnClaim.Status.REJECTED,
                actor=self.manager,
            )

    def test_rejection_records_reason_and_time(self):
        self.claim.status = ReturnClaim.Status.TRIAGE
        self.claim.save()
        rejected = transition_claim(
            claim=self.claim,
            target_status=ReturnClaim.Status.REJECTED,
            actor=self.manager,
            rejection_reason="Warranty expired.",
        )
        self.assertEqual(rejected.rejection_reason, "Warranty expired.")
        self.assertIsNotNone(rejected.rejected_at)

    def test_inspection_requires_role_and_received_state(self):
        with self.assertRaises(ValidationError):
            self.add_inspection()
        self.move_to_received()
        with self.assertRaises(PermissionDenied):
            self.add_inspection(actor=self.viewer)

    def test_inspection_moves_claim_and_writes_event(self):
        self.move_to_received()
        inspection = self.add_inspection()
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ReturnClaim.Status.INSPECTING)
        self.assertTrue(inspection.fault_confirmed)
        self.assertTrue(self.claim.events.filter(message__icontains="confirmed").exists())

    def test_inspection_can_be_updated(self):
        self.move_to_received()
        first = self.add_inspection()
        updated = record_inspection(
            claim=self.claim,
            actor=self.manager,
            condition=Inspection.Condition.DAMAGED,
            fault_confirmed=False,
            findings="No electrical fault after extended test.",
            recommendation=Inspection.Recommendation.NO_FAULT,
        )
        self.assertEqual(first.pk, updated.pk)
        self.assertEqual(updated.technician, self.manager)

    def test_resolution_requires_inspection(self):
        self.claim.status = ReturnClaim.Status.INSPECTING
        self.claim.save()
        with self.assertRaises(ValidationError):
            transition_claim(
                claim=self.claim,
                target_status=ReturnClaim.Status.RESOLVED,
                actor=self.manager,
                resolution=ReturnClaim.Resolution.REPAIRED,
                resolution_summary="Repair complete.",
            )

    def test_resolution_and_close_happy_path(self):
        self.move_to_received()
        self.add_inspection()
        resolved = transition_claim(
            claim=self.claim,
            target_status=ReturnClaim.Status.RESOLVED,
            actor=self.manager,
            resolution=ReturnClaim.Resolution.REFUNDED,
            resolution_summary="A full refund was approved.",
            resolution_amount=Decimal("12000.00"),
        )
        closed = transition_claim(
            claim=resolved,
            target_status=ReturnClaim.Status.CLOSED,
            actor=self.owner,
            message="Customer confirmed receipt.",
        )
        self.assertEqual(closed.status, ReturnClaim.Status.CLOSED)
        self.assertIsNotNone(closed.resolved_at)
        self.assertIsNotNone(closed.closed_at)

    def test_replacement_resolution_requires_reference(self):
        self.move_to_received()
        self.add_inspection()
        with self.assertRaises(ValidationError):
            transition_claim(
                claim=self.claim,
                target_status=ReturnClaim.Status.RESOLVED,
                actor=self.manager,
                resolution=ReturnClaim.Resolution.REPLACED,
                resolution_summary="Replacement approved.",
            )


class FormAndViewTests(ReturnRelayTestCase):
    def test_landing_and_login_render_for_anonymous_user(self):
        self.assertContains(self.client.get(reverse("landing")), "every return into trust")
        self.assertContains(self.client.get(reverse("login")), "Welcome back")

    def test_authenticated_landing_redirects_to_dashboard(self):
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.get(reverse("landing")), reverse("dashboard"))

    def test_signup_creates_unique_owner_workspace(self):
        Organization.objects.create(name="Acme", slug="acme")
        response = self.client.post(
            reverse("signup"),
            {
                "workspace_name": "Acme",
                "username": "new-owner",
                "email": "owner@acme.example",
                "password1": "VeryStrongPass123!",
                "password2": "VeryStrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        membership = Membership.objects.get(user__username="new-owner")
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(membership.organization.slug, "acme-2")

    def test_signup_form_can_defer_workspace_creation(self):
        form = SignupForm(
            data={
                "workspace_name": "Deferred",
                "username": "deferred",
                "email": "deferred@example.com",
                "password1": "VeryStrongPass123!",
                "password2": "VeryStrongPass123!",
            }
        )
        self.assertTrue(form.is_valid())
        form.save(commit=False)
        self.assertFalse(Organization.objects.filter(name="Deferred").exists())

    def test_workspace_page_redirects_anonymous_user(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_user_without_membership_is_forbidden(self):
        outsider = User.objects.create_user("outsider", password="StrongPass123!")
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)

    def test_dashboard_and_read_pages_render(self):
        self.client.force_login(self.viewer)
        for name in ["dashboard", "claim_list", "catalog", "customer_list", "team_list"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_claim_search_and_filters(self):
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse("claim_list"),
            {"q": "SERIAL-100", "status": "submitted", "priority": "high"},
        )
        self.assertContains(response, self.claim.tracking_code)
        response = self.client.get(reverse("claim_list"), {"q": "missing"})
        self.assertNotContains(response, self.claim.tracking_code)

    def test_cross_tenant_claim_is_not_visible(self):
        self.client.force_login(self.other_user)
        self.assertEqual(
            self.client.get(reverse("claim_detail", args=[self.claim.pk])).status_code, 404
        )

    def test_viewer_cannot_open_manager_pages(self):
        self.client.force_login(self.viewer)
        for name in [
            "claim_create",
            "product_create",
            "item_create",
            "customer_create",
            "team_create",
        ]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_manager_can_create_customer_and_product(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("customer_create"),
            {
                "name": "New Customer",
                "contact_name": "Nina",
                "email": "nina@example.com",
                "phone": "555-0199",
            },
        )
        self.assertRedirects(response, reverse("customer_list"))
        response = self.client.post(
            reverse("product_create"),
            {
                "sku": " new-200 ",
                "name": "New product",
                "category": Product.Category.OTHER,
                "retail_price": "99.50",
                "warranty_months": 6,
                "active": "on",
            },
        )
        self.assertRedirects(response, reverse("catalog"))
        self.assertTrue(Product.objects.filter(sku="NEW-200").exists())

    def test_manager_can_register_item_and_open_claim(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("item_create"),
            {
                "product": self.product.pk,
                "customer": self.customer.pk,
                "serial_number": " new-serial ",
                "order_reference": "NEW-ORDER",
                "purchase_date": timezone.localdate().isoformat(),
            },
        )
        self.assertRedirects(response, reverse("catalog"))
        new_item = RegisteredItem.objects.get(serial_number="NEW-SERIAL")
        response = self.client.post(
            reverse("claim_create"),
            {
                "item": new_item.pk,
                "issue_category": ReturnClaim.IssueCategory.OTHER,
                "description": "A sufficiently detailed product issue.",
                "evidence_url": "https://example.com/evidence",
                "requested_remedy": ReturnClaim.Remedy.REPAIR,
                "priority": ReturnClaim.Priority.NORMAL,
            },
        )
        created = ReturnClaim.objects.exclude(pk=self.claim.pk).get()
        self.assertRedirects(response, reverse("claim_detail", args=[created.pk]))
        self.assertTrue(created.tracking_code.startswith("RMA-"))

    def test_manager_can_create_team_member(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("team_create"),
            {
                "username": "new-tech",
                "first_name": "New",
                "last_name": "Tech",
                "email": "tech@example.com",
                "role": Membership.Role.TECHNICIAN,
                "title": "Repair technician",
                "temporary_password": "StrongPass456!",
            },
        )
        self.assertRedirects(response, reverse("team_list"))
        self.assertEqual(
            User.objects.get(username="new-tech").returnrelay_membership.organization,
            self.organization,
        )

    def test_team_form_rejects_duplicate_user_and_weak_password(self):
        duplicate = TeamMemberForm(
            data={
                "username": self.viewer.username,
                "first_name": "Duplicate",
                "last_name": "User",
                "email": "duplicate@example.com",
                "role": Membership.Role.VIEWER,
                "title": "Viewer",
                "temporary_password": "password",
            },
            organization=self.organization,
        )
        self.assertFalse(duplicate.is_valid())
        self.assertIn("username", duplicate.errors)
        self.assertIn("temporary_password", duplicate.errors)

    def test_forms_scope_item_relations_to_tenant(self):
        form = RegisteredItemForm(organization=self.other_organization)
        self.assertNotIn(self.product, form.fields["product"].queryset)
        self.assertNotIn(self.customer, form.fields["customer"].queryset)
        product_form = ProductForm(
            data={"sku": " mixed-case ", "name": "Name"},
            organization=self.other_organization,
        )
        self.assertFalse(product_form.is_valid())

    def test_customer_form_rejects_duplicate_name_in_same_tenant(self):
        form = CustomerForm(
            data={
                "name": "acme café",
                "contact_name": "Another contact",
                "email": "another@example.com",
                "phone": "555-0200",
            },
            organization=self.organization,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_product_form_rejects_duplicate_sku_in_same_tenant(self):
        form = ProductForm(
            data={
                "sku": " cof-100 ",
                "name": "Duplicate",
                "category": Product.Category.OTHER,
                "retail_price": "20.00",
                "warranty_months": 12,
                "active": "on",
            },
            organization=self.organization,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("sku", form.errors)

    def test_registered_item_form_rejects_duplicate_serial_in_same_tenant(self):
        form = RegisteredItemForm(
            data={
                "product": self.product.pk,
                "customer": self.customer.pk,
                "serial_number": " serial-100 ",
                "order_reference": "NEW-ORDER",
                "purchase_date": timezone.localdate().isoformat(),
            },
            organization=self.organization,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("serial_number", form.errors)

    def test_manager_transition_view_updates_claim(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("claim_transition", args=[self.claim.pk]),
            {
                "status": ReturnClaim.Status.TRIAGE,
                "update_message": "Eligibility review started.",
                "visible_to_customer": "on",
            },
        )
        self.assertRedirects(response, reverse("claim_detail", args=[self.claim.pk]))
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, ReturnClaim.Status.TRIAGE)

    def test_invalid_transition_view_returns_400(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("claim_transition", args=[self.claim.pk]), {"status": "closed"}
        )
        self.assertEqual(response.status_code, 400)

    def test_inspection_view_enforces_status_and_role(self):
        self.client.force_login(self.technician)
        self.assertEqual(
            self.client.get(reverse("claim_inspect", args=[self.claim.pk])).status_code, 403
        )
        self.move_to_received()
        response = self.client.post(
            reverse("claim_inspect", args=[self.claim.pk]),
            {
                "condition": Inspection.Condition.USED,
                "fault_confirmed": "on",
                "findings": "A failed relay reproduces the issue.",
                "recommendation": Inspection.Recommendation.REPAIR,
                "customer_update": "We found the reported fault.",
                "visible_to_customer": "on",
            },
        )
        self.assertRedirects(response, reverse("claim_detail", args=[self.claim.pk]))
        self.assertTrue(Inspection.objects.filter(claim=self.claim).exists())

    def test_public_tracking_hides_internal_event(self):
        ClaimEvent.objects.create(
            organization=self.organization,
            claim=self.claim,
            actor=self.owner,
            status=self.claim.status,
            message="Customer-safe message",
            visible_to_customer=True,
        )
        ClaimEvent.objects.create(
            organization=self.organization,
            claim=self.claim,
            actor=self.owner,
            status=self.claim.status,
            message="Secret internal note",
            visible_to_customer=False,
        )
        response = self.client.get(
            reverse("public_tracking", args=[self.organization.slug, self.claim.tracking_code])
        )
        self.assertContains(response, "Customer-safe message")
        self.assertNotContains(response, "Secret internal note")
        self.assertNotContains(response, self.item.serial_number)


class ApiAndSeedTests(ReturnRelayTestCase):
    def test_api_requires_authentication(self):
        self.assertEqual(self.client.get(reverse("api_summary")).status_code, 302)

    def test_summary_api_is_tenant_scoped(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("api_summary"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workspace"], self.organization.name)
        self.assertEqual(response.json()["claims"][ReturnClaim.Status.SUBMITTED], 1)

    def test_claim_api_filters_and_serializes_business_flags(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("api_claims"), {"status": ReturnClaim.Status.SUBMITTED})
        result = response.json()["results"][0]
        self.assertEqual(result["tracking_code"], self.claim.tracking_code)
        self.assertTrue(result["in_warranty"])

    def test_catalog_api_is_tenant_scoped(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("api_catalog"))
        self.assertEqual(response.json()["results"][0]["sku"], self.product.sku)

    def test_transition_api_rejects_invalid_json(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("api_transition", args=[self.claim.pk]),
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_transition_api_enforces_role(self):
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse("api_transition", args=[self.claim.pk]),
            data=json.dumps({"status": ReturnClaim.Status.TRIAGE}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_transition_api_returns_validation_error(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("api_transition", args=[self.claim.pk]),
            data=json.dumps({"status": ReturnClaim.Status.RESOLVED}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_transition_api_updates_claim(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("api_transition", args=[self.claim.pk]),
            data=json.dumps(
                {
                    "status": ReturnClaim.Status.TRIAGE,
                    "message": "API triage update",
                    "visible_to_customer": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], ReturnClaim.Status.TRIAGE)

    def test_demo_seed_is_idempotent_and_complete(self):
        call_command("seed_demo")
        counts = (
            Organization.objects.count(),
            Product.objects.filter(organization__slug="summit-appliances").count(),
            ReturnClaim.objects.filter(organization__slug="summit-appliances").count(),
        )
        call_command("seed_demo")
        self.assertEqual(
            counts,
            (
                Organization.objects.count(),
                Product.objects.filter(organization__slug="summit-appliances").count(),
                ReturnClaim.objects.filter(organization__slug="summit-appliances").count(),
            ),
        )
        self.assertTrue(User.objects.get(username="demo_claims").check_password("DemoPass123!"))
