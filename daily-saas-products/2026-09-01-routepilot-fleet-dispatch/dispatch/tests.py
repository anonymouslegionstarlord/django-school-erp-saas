import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import DriverCreateForm, SignupForm
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
from .services import assign_shipment, transition_choices, transition_shipment


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RoutePilotTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Northstar", slug="northstar")
        self.other_organization = Organization.objects.create(name="Elsewhere", slug="elsewhere")
        self.owner = self.make_user("owner", Membership.Role.OWNER)
        self.dispatcher = self.make_user("dispatcher", Membership.Role.DISPATCHER)
        self.driver_user = self.make_user("driver", Membership.Role.DRIVER)
        self.viewer = self.make_user("viewer", Membership.Role.VIEWER)
        self.other_user = self.make_user(
            "other", Membership.Role.OWNER, organization=self.other_organization
        )
        self.driver = DriverProfile.objects.create(
            organization=self.organization,
            user=self.driver_user,
            license_number="DL-100",
            license_expiry=timezone.localdate() + timedelta(days=365),
            phone="123456789",
        )
        self.vehicle = Vehicle.objects.create(
            organization=self.organization,
            registration="RP-100",
            name="Van 100",
            kind=Vehicle.Kind.VAN,
            capacity_kg=Decimal("1000"),
            odometer_km=1000,
            next_service_km=5000,
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            name="Acme",
            contact_name="Alex",
            email="alex@example.com",
            phone="555-0100",
        )
        self.shipment = Shipment.objects.create(
            organization=self.organization,
            tracking_code="RP-TEST-001",
            customer=self.customer,
            pickup_address="Warehouse A",
            delivery_address="Customer B",
            package_description="Test cartons",
            weight_kg=Decimal("120"),
            priority=Shipment.Priority.EXPRESS,
            scheduled_pickup=timezone.now() + timedelta(hours=1),
            delivery_deadline=timezone.now() + timedelta(hours=5),
            created_by=self.owner,
        )

    def make_user(self, username, role, organization=None):
        user = User.objects.create_user(username=username, password="StrongPass123!")
        Membership.objects.create(
            user=user,
            organization=organization or self.organization,
            role=role,
        )
        return user

    def assign(self, shipment=None, driver=None, vehicle=None, actor=None):
        return assign_shipment(
            shipment=shipment or self.shipment,
            driver=driver or self.driver,
            vehicle=vehicle or self.vehicle,
            actor=actor or self.dispatcher,
        )


class ModelTests(RoutePilotTestCase):
    def test_membership_permissions_follow_role(self):
        self.assertTrue(self.owner.routepilot_membership.can_manage)
        self.assertTrue(self.dispatcher.routepilot_membership.can_dispatch)
        self.assertFalse(self.driver_user.routepilot_membership.can_manage)
        self.assertFalse(self.viewer.routepilot_membership.can_dispatch)

    def test_driver_requires_driver_membership_in_same_tenant(self):
        profile = DriverProfile(
            organization=self.organization,
            user=self.viewer,
            license_number="DL-BAD",
            license_expiry=timezone.localdate() + timedelta(days=1),
            phone="123",
        )
        with self.assertRaises(ValidationError):
            profile.full_clean()

    def test_driver_license_validity_is_date_aware(self):
        self.assertTrue(self.driver.is_license_valid)
        self.driver.license_expiry = timezone.localdate() - timedelta(days=1)
        self.assertFalse(self.driver.is_license_valid)

    def test_vehicle_service_due_uses_odometer(self):
        self.assertFalse(self.vehicle.is_service_due)
        self.vehicle.odometer_km = self.vehicle.next_service_km
        self.assertTrue(self.vehicle.is_service_due)

    def test_vehicle_requires_positive_capacity(self):
        self.vehicle.capacity_kg = Decimal("0")
        with self.assertRaises(ValidationError):
            self.vehicle.full_clean()

    def test_vehicle_registration_is_unique_per_tenant(self):
        duplicate = Vehicle(
            organization=self.organization,
            registration=self.vehicle.registration,
            name="Duplicate",
            kind=Vehicle.Kind.VAN,
            capacity_kg=Decimal("50"),
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_shipment_rejects_cross_tenant_customer(self):
        other_customer = Customer.objects.create(
            organization=self.other_organization,
            name="Other customer",
            contact_name="Other",
            email="other@example.com",
            phone="555",
        )
        self.shipment.customer = other_customer
        with self.assertRaises(ValidationError):
            self.shipment.full_clean()

    def test_shipment_rejects_invalid_deadline(self):
        self.shipment.delivery_deadline = self.shipment.scheduled_pickup
        with self.assertRaises(ValidationError):
            self.shipment.full_clean()

    def test_shipment_rejects_cross_tenant_creator(self):
        self.shipment.created_by = self.other_user
        with self.assertRaises(ValidationError):
            self.shipment.full_clean()

    def test_delivered_shipment_requires_proof_fields(self):
        self.shipment.status = Shipment.Status.DELIVERED
        with self.assertRaises(ValidationError) as context:
            self.shipment.full_clean()
        self.assertIn("delivery_reference", context.exception.message_dict)
        self.assertIn("proof_note", context.exception.message_dict)
        self.assertIn("delivered_at", context.exception.message_dict)

    def test_failed_shipment_requires_reason(self):
        self.shipment.status = Shipment.Status.FAILED
        with self.assertRaises(ValidationError):
            self.shipment.full_clean()

    def test_shipment_active_and_overdue_properties(self):
        self.shipment.status = Shipment.Status.IN_TRANSIT
        self.assertTrue(self.shipment.is_active)
        self.shipment.delivery_deadline = timezone.now() - timedelta(minutes=1)
        self.assertTrue(self.shipment.is_overdue)
        self.shipment.status = Shipment.Status.DELIVERED
        self.assertFalse(self.shipment.is_overdue)

    def test_tracking_code_is_unique_per_tenant(self):
        duplicate = Shipment(
            organization=self.organization,
            tracking_code=self.shipment.tracking_code,
            customer=self.customer,
            pickup_address="A",
            delivery_address="B",
            package_description="Duplicate",
            weight_kg=Decimal("1"),
            scheduled_pickup=timezone.now(),
            delivery_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.owner,
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_assignment_rejects_capacity_shortfall(self):
        self.vehicle.capacity_kg = Decimal("10")
        assignment = DispatchAssignment(
            organization=self.organization,
            shipment=self.shipment,
            driver=self.driver,
            vehicle=self.vehicle,
            assigned_by=self.dispatcher,
        )
        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_assignment_rejects_cross_tenant_resources(self):
        other_driver_user = self.make_user(
            "other-driver", Membership.Role.DRIVER, self.other_organization
        )
        other_driver = DriverProfile.objects.create(
            organization=self.other_organization,
            user=other_driver_user,
            license_number="OTHER-DL",
            license_expiry=timezone.localdate() + timedelta(days=10),
            phone="555",
        )
        assignment = DispatchAssignment(
            organization=self.organization,
            shipment=self.shipment,
            driver=other_driver,
            vehicle=self.vehicle,
            assigned_by=self.dispatcher,
        )
        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_assignment_rejects_expired_license_and_non_dispatcher(self):
        self.driver.license_expiry = timezone.localdate() - timedelta(days=1)
        assignment = DispatchAssignment(
            organization=self.organization,
            shipment=self.shipment,
            driver=self.driver,
            vehicle=self.vehicle,
            assigned_by=self.viewer,
        )
        with self.assertRaises(ValidationError) as context:
            assignment.full_clean()
        self.assertIn("driver", context.exception.message_dict)
        self.assertIn("assigned_by", context.exception.message_dict)

    def test_event_rejects_cross_tenant_actor(self):
        event = ShipmentEvent(
            organization=self.organization,
            shipment=self.shipment,
            actor=self.other_user,
            status=Shipment.Status.UNASSIGNED,
            message="Nope",
        )
        with self.assertRaises(ValidationError):
            event.full_clean()


class ServiceTests(RoutePilotTestCase):
    def test_assign_shipment_updates_status_and_resources(self):
        assignment = self.assign()
        self.shipment.refresh_from_db()
        self.driver.refresh_from_db()
        self.vehicle.refresh_from_db()
        self.assertEqual(assignment.shipment, self.shipment)
        self.assertEqual(self.shipment.status, Shipment.Status.ASSIGNED)
        self.assertEqual(self.driver.status, DriverProfile.Status.ON_ROUTE)
        self.assertEqual(self.vehicle.status, Vehicle.Status.ON_ROUTE)

    def test_assignment_records_customer_visible_event(self):
        self.assign()
        event = self.shipment.events.get()
        self.assertEqual(event.status, Shipment.Status.ASSIGNED)
        self.assertTrue(event.visible_to_customer)
        self.assertIn(self.vehicle.registration, event.message)

    def test_only_dispatchers_can_assign(self):
        with self.assertRaises(PermissionDenied):
            self.assign(actor=self.viewer)

    def test_unavailable_driver_cannot_be_assigned(self):
        self.driver.status = DriverProfile.Status.OFF_DUTY
        self.driver.save()
        with self.assertRaises(ValidationError):
            self.assign()

    def test_maintenance_vehicle_cannot_be_assigned(self):
        self.vehicle.status = Vehicle.Status.MAINTENANCE
        self.vehicle.save()
        with self.assertRaises(ValidationError):
            self.assign()

    def test_service_due_vehicle_cannot_be_assigned(self):
        self.vehicle.odometer_km = self.vehicle.next_service_km
        self.vehicle.save()
        with self.assertRaises(ValidationError):
            self.assign()

    def test_capacity_shortfall_cannot_be_assigned(self):
        self.vehicle.capacity_kg = Decimal("20")
        self.vehicle.save()
        with self.assertRaises(ValidationError):
            self.assign()

    def test_delivered_shipment_cannot_be_reassigned(self):
        self.shipment.status = Shipment.Status.DELIVERED
        self.shipment.delivered_at = timezone.now()
        self.shipment.delivery_reference = "POD"
        self.shipment.proof_note = "Received"
        self.shipment.save()
        with self.assertRaises(ValidationError):
            self.assign()

    def test_reassignment_releases_previous_resources(self):
        self.assign()
        second_driver_user = self.make_user("driver-two", Membership.Role.DRIVER)
        second_driver = DriverProfile.objects.create(
            organization=self.organization,
            user=second_driver_user,
            license_number="DL-200",
            license_expiry=timezone.localdate() + timedelta(days=90),
            phone="555",
        )
        second_vehicle = Vehicle.objects.create(
            organization=self.organization,
            registration="RP-200",
            name="Van 200",
            kind=Vehicle.Kind.VAN,
            capacity_kg=Decimal("900"),
        )
        assign_shipment(
            shipment=self.shipment,
            driver=second_driver,
            vehicle=second_vehicle,
            actor=self.owner,
        )
        self.driver.refresh_from_db()
        self.vehicle.refresh_from_db()
        second_driver.refresh_from_db()
        self.assertEqual(self.driver.status, DriverProfile.Status.AVAILABLE)
        self.assertEqual(self.vehicle.status, Vehicle.Status.AVAILABLE)
        self.assertEqual(second_driver.status, DriverProfile.Status.ON_ROUTE)

    def test_driver_can_follow_happy_path(self):
        self.assign()
        transition_shipment(
            shipment=self.shipment,
            target_status=Shipment.Status.PICKED_UP,
            actor=self.driver_user,
            message="Collected",
        )
        transition_shipment(
            shipment=self.shipment,
            target_status=Shipment.Status.IN_TRANSIT,
            actor=self.driver_user,
        )
        delivered = transition_shipment(
            shipment=self.shipment,
            target_status=Shipment.Status.DELIVERED,
            actor=self.driver_user,
            delivery_reference="POD-1",
            proof_note="Signed by Alex",
        )
        self.assertEqual(delivered.status, Shipment.Status.DELIVERED)
        self.assertIsNotNone(delivered.delivered_at)
        self.driver.refresh_from_db()
        self.vehicle.refresh_from_db()
        self.assertEqual(self.driver.status, DriverProfile.Status.AVAILABLE)
        self.assertEqual(self.vehicle.status, Vehicle.Status.AVAILABLE)

    def test_delivery_requires_reference_and_proof(self):
        self.assign()
        self.shipment.status = Shipment.Status.IN_TRANSIT
        self.shipment.save()
        with self.assertRaises(ValidationError):
            transition_shipment(
                shipment=self.shipment,
                target_status=Shipment.Status.DELIVERED,
                actor=self.driver_user,
            )

    def test_failed_delivery_requires_reason_and_releases_resources(self):
        self.assign()
        self.shipment.status = Shipment.Status.IN_TRANSIT
        self.shipment.save()
        with self.assertRaises(ValidationError):
            transition_shipment(
                shipment=self.shipment,
                target_status=Shipment.Status.FAILED,
                actor=self.driver_user,
            )
        transition_shipment(
            shipment=self.shipment,
            target_status=Shipment.Status.FAILED,
            actor=self.driver_user,
            failure_reason="Recipient unavailable",
        )
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.status, DriverProfile.Status.AVAILABLE)

    def test_driver_cannot_update_another_drivers_route(self):
        self.assign()
        unrelated = self.make_user("unrelated-driver", Membership.Role.DRIVER)
        with self.assertRaises(PermissionDenied):
            transition_shipment(
                shipment=self.shipment,
                target_status=Shipment.Status.PICKED_UP,
                actor=unrelated,
            )

    def test_viewer_cannot_transition(self):
        self.assign()
        with self.assertRaises(PermissionDenied):
            transition_shipment(
                shipment=self.shipment,
                target_status=Shipment.Status.PICKED_UP,
                actor=self.viewer,
            )

    def test_driver_cannot_cancel(self):
        self.assign()
        with self.assertRaises(PermissionDenied):
            transition_shipment(
                shipment=self.shipment,
                target_status=Shipment.Status.CANCELLED,
                actor=self.driver_user,
            )

    def test_invalid_transition_is_rejected(self):
        self.assign()
        with self.assertRaises(ValidationError):
            transition_shipment(
                shipment=self.shipment,
                target_status=Shipment.Status.DELIVERED,
                actor=self.dispatcher,
                delivery_reference="POD",
                proof_note="Proof",
            )

    def test_dispatcher_can_cancel_and_resources_are_released(self):
        self.assign()
        transition_shipment(
            shipment=self.shipment,
            target_status=Shipment.Status.CANCELLED,
            actor=self.dispatcher,
        )
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.status, DriverProfile.Status.AVAILABLE)

    def test_transition_choices_are_role_aware(self):
        self.assign()
        manager_choices = dict(
            transition_choices(self.shipment, self.dispatcher.routepilot_membership)
        )
        driver_choices = dict(
            transition_choices(self.shipment, self.driver_user.routepilot_membership)
        )
        self.assertIn(Shipment.Status.CANCELLED, manager_choices)
        self.assertNotIn(Shipment.Status.CANCELLED, driver_choices)


class FormTests(RoutePilotTestCase):
    def test_signup_creates_owner_and_unique_workspace_slug(self):
        Organization.objects.create(name="Fleet", slug="fleet")
        form = SignupForm(
            data={
                "workspace_name": "Fleet",
                "username": "new-owner",
                "email": "owner@fleet.example",
                "password1": "ComplicatedPass123!",
                "password2": "ComplicatedPass123!",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.routepilot_membership.role, Membership.Role.OWNER)
        self.assertEqual(user.routepilot_membership.organization.slug, "fleet-2")

    def test_driver_form_creates_login_membership_and_profile(self):
        form = DriverCreateForm(
            organization=self.organization,
            data={
                "username": "new-driver",
                "first_name": "New",
                "last_name": "Driver",
                "email": "new@example.com",
                "temporary_password": "StrongDriverPass123!",
                "license_number": "dl-new",
                "license_expiry": (timezone.localdate() + timedelta(days=100)).isoformat(),
                "phone": "555-1200",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        driver = form.save()
        self.assertEqual(driver.license_number, "DL-NEW")
        self.assertEqual(driver.user.routepilot_membership.role, Membership.Role.DRIVER)
        self.assertTrue(driver.user.check_password("StrongDriverPass123!"))

    def test_driver_form_rejects_duplicate_username(self):
        form = DriverCreateForm(
            organization=self.organization,
            data={
                "username": self.driver_user.username,
                "first_name": "Dup",
                "last_name": "User",
                "email": "dup@example.com",
                "temporary_password": "StrongDriverPass123!",
                "license_number": "DL-NEW",
                "license_expiry": (timezone.localdate() + timedelta(days=100)).isoformat(),
                "phone": "555",
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)


class ViewAndApiTests(RoutePilotTestCase):
    def test_landing_is_public_and_authenticated_users_redirect(self):
        self.assertEqual(self.client.get(reverse("landing")).status_code, 200)
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.get(reverse("landing")), reverse("dashboard"))

    def test_protected_views_redirect_anonymous_users(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_authenticated_user_without_membership_gets_forbidden(self):
        orphan = User.objects.create_user("orphan", password="StrongPass123!")
        self.client.force_login(orphan)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)

    def test_dashboard_and_lists_render_for_workspace_member(self):
        self.client.force_login(self.owner)
        for name in ["dashboard", "shipment_list", "customer_list", "fleet_list"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_shipment_list_is_tenant_isolated(self):
        other_customer = Customer.objects.create(
            organization=self.other_organization,
            name="Hidden customer",
            contact_name="Hidden",
            email="hidden@example.com",
            phone="555",
        )
        hidden = Shipment.objects.create(
            organization=self.other_organization,
            tracking_code="HIDDEN-1",
            customer=other_customer,
            pickup_address="A",
            delivery_address="B",
            package_description="Hidden",
            weight_kg=Decimal("1"),
            scheduled_pickup=timezone.now(),
            delivery_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.other_user,
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse("shipment_list"))
        self.assertContains(response, self.shipment.tracking_code)
        self.assertNotContains(response, hidden.tracking_code)
        self.assertEqual(
            self.client.get(reverse("shipment_detail", args=[hidden.pk])).status_code, 404
        )

    def test_driver_sees_only_assigned_shipments(self):
        unassigned = Shipment.objects.create(
            organization=self.organization,
            tracking_code="RP-UNASSIGNED",
            customer=self.customer,
            pickup_address="A",
            delivery_address="B",
            package_description="Hidden from driver",
            weight_kg=Decimal("10"),
            scheduled_pickup=timezone.now(),
            delivery_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.owner,
        )
        self.assign()
        self.client.force_login(self.driver_user)
        response = self.client.get(reverse("shipment_list"))
        self.assertContains(response, self.shipment.tracking_code)
        self.assertNotContains(response, unassigned.tracking_code)

    def test_viewer_cannot_open_manager_create_views(self):
        self.client.force_login(self.viewer)
        for name in ["shipment_create", "customer_create", "vehicle_create", "driver_create"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_manager_can_create_customer_and_shipment(self):
        self.client.force_login(self.dispatcher)
        response = self.client.post(
            reverse("customer_create"),
            {
                "name": "New customer",
                "contact_name": "Nora",
                "email": "nora@example.com",
                "phone": "555",
                "notes": "",
            },
        )
        self.assertRedirects(response, reverse("customer_list"))
        customer = Customer.objects.get(name="New customer")
        response = self.client.post(
            reverse("shipment_create"),
            {
                "tracking_code": "rp-new-002",
                "customer": customer.pk,
                "pickup_address": "Origin",
                "delivery_address": "Destination",
                "package_description": "Parcel",
                "weight_kg": "12.5",
                "priority": Shipment.Priority.STANDARD,
                "scheduled_pickup": (timezone.now() + timedelta(hours=1)).strftime(
                    "%Y-%m-%dT%H:%M"
                ),
                "delivery_deadline": (timezone.now() + timedelta(hours=3)).strftime(
                    "%Y-%m-%dT%H:%M"
                ),
            },
        )
        shipment = Shipment.objects.get(tracking_code="RP-NEW-002")
        self.assertRedirects(response, reverse("shipment_detail", args=[shipment.pk]))
        self.assertEqual(shipment.organization, self.organization)

    def test_manager_can_assign_through_view(self):
        self.client.force_login(self.dispatcher)
        response = self.client.post(
            reverse("shipment_assign", args=[self.shipment.pk]),
            {"driver": self.driver.pk, "vehicle": self.vehicle.pk},
        )
        self.assertRedirects(response, reverse("shipment_detail", args=[self.shipment.pk]))
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, Shipment.Status.ASSIGNED)

    def test_driver_can_advance_status_through_view(self):
        self.assign()
        self.client.force_login(self.driver_user)
        response = self.client.post(
            reverse("shipment_transition", args=[self.shipment.pk]),
            {
                "status": Shipment.Status.PICKED_UP,
                "update_message": "Collected",
                "delivery_reference": "",
                "proof_note": "",
                "failure_reason": "",
                "visible_to_customer": "on",
            },
        )
        self.assertRedirects(response, reverse("shipment_detail", args=[self.shipment.pk]))
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, Shipment.Status.PICKED_UP)

    def test_public_tracking_hides_internal_updates_and_addresses(self):
        ShipmentEvent.objects.create(
            organization=self.organization,
            shipment=self.shipment,
            actor=self.dispatcher,
            status=self.shipment.status,
            message="Customer update",
            visible_to_customer=True,
        )
        ShipmentEvent.objects.create(
            organization=self.organization,
            shipment=self.shipment,
            actor=self.dispatcher,
            status=self.shipment.status,
            message="Internal secret",
            visible_to_customer=False,
        )
        response = self.client.get(
            reverse(
                "public_tracking",
                args=[self.organization.slug, self.shipment.tracking_code],
            )
        )
        self.assertContains(response, "Customer update")
        self.assertNotContains(response, "Internal secret")
        self.assertNotContains(response, self.shipment.delivery_address)

    def test_api_requires_authentication(self):
        self.assertEqual(self.client.get(reverse("api_summary")).status_code, 302)

    def test_summary_api_is_tenant_scoped(self):
        self.client.force_login(self.owner)
        payload = self.client.get(reverse("api_summary")).json()
        self.assertEqual(payload["workspace"], self.organization.name)
        self.assertEqual(payload["shipments"][Shipment.Status.UNASSIGNED], 1)
        self.assertEqual(payload["role"], Membership.Role.OWNER)

    def test_shipments_api_filters_status_and_serializes_assignment(self):
        self.assign()
        self.client.force_login(self.owner)
        response = self.client.get(reverse("api_shipments"), {"status": Shipment.Status.ASSIGNED})
        result = response.json()["results"][0]
        self.assertEqual(result["tracking_code"], self.shipment.tracking_code)
        self.assertEqual(result["assignment"]["vehicle"], self.vehicle.registration)

    def test_driver_shipments_api_hides_unassigned_work(self):
        self.client.force_login(self.driver_user)
        self.assertEqual(self.client.get(reverse("api_shipments")).json()["results"], [])

    def test_fleet_api_returns_readiness_without_other_tenants(self):
        Vehicle.objects.create(
            organization=self.other_organization,
            registration="OTHER",
            name="Hidden",
            kind=Vehicle.Kind.VAN,
            capacity_kg=Decimal("100"),
        )
        self.client.force_login(self.viewer)
        payload = self.client.get(reverse("api_fleet")).json()
        self.assertEqual(len(payload["vehicles"]), 1)
        self.assertEqual(payload["vehicles"][0]["registration"], self.vehicle.registration)

    def test_transition_api_rejects_invalid_json(self):
        self.assign()
        self.client.force_login(self.driver_user)
        response = self.client.post(
            reverse("api_transition", args=[self.shipment.pk]),
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_transition_api_updates_assigned_drivers_shipment(self):
        self.assign()
        self.client.force_login(self.driver_user)
        response = self.client.post(
            reverse("api_transition", args=[self.shipment.pk]),
            data=json.dumps({"status": Shipment.Status.PICKED_UP, "message": "Loaded"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], Shipment.Status.PICKED_UP)

    def test_transition_api_enforces_viewer_permission(self):
        self.assign()
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse("api_transition", args=[self.shipment.pk]),
            data=json.dumps({"status": Shipment.Status.PICKED_UP}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_search_filters_shipments(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("shipment_list"), {"q": "Acme"})
        self.assertContains(response, self.shipment.tracking_code)
        response = self.client.get(reverse("shipment_list"), {"q": "missing"})
        self.assertNotContains(response, self.shipment.tracking_code)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DemoCommandTests(TestCase):
    def test_seed_demo_is_idempotent_and_creates_working_accounts(self):
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)
        self.assertEqual(Organization.objects.filter(slug="northstar-logistics").count(), 1)
        self.assertEqual(
            Shipment.objects.filter(organization__slug="northstar-logistics").count(), 4
        )
        dispatcher = User.objects.get(username="demo_dispatcher")
        self.assertTrue(dispatcher.check_password("DemoPass123!"))
        self.assertEqual(dispatcher.routepilot_membership.role, Membership.Role.DISPATCHER)
