from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    DispatchAssignment,
    DriverProfile,
    Membership,
    Shipment,
    ShipmentEvent,
    Vehicle,
)

ALLOWED_TRANSITIONS = {
    Shipment.Status.UNASSIGNED: {Shipment.Status.CANCELLED},
    Shipment.Status.ASSIGNED: {Shipment.Status.PICKED_UP, Shipment.Status.CANCELLED},
    Shipment.Status.PICKED_UP: {
        Shipment.Status.IN_TRANSIT,
        Shipment.Status.FAILED,
        Shipment.Status.CANCELLED,
    },
    Shipment.Status.IN_TRANSIT: {
        Shipment.Status.DELIVERED,
        Shipment.Status.FAILED,
        Shipment.Status.CANCELLED,
    },
    Shipment.Status.DELIVERED: set(),
    Shipment.Status.FAILED: set(),
    Shipment.Status.CANCELLED: set(),
}


def transition_choices(shipment, membership):
    choices = ALLOWED_TRANSITIONS.get(shipment.status, set())
    if not membership.can_dispatch:
        choices = choices - {Shipment.Status.CANCELLED}
    return [
        (value, Shipment.Status(value).label)
        for value in Shipment.Status.values
        if value in choices
    ]


def _release_assignment_resources(shipment):
    assignment = getattr(shipment, "assignment", None)
    if assignment is None:
        return
    assignment.driver.status = DriverProfile.Status.AVAILABLE
    assignment.driver.save(update_fields=["status"])
    assignment.vehicle.status = Vehicle.Status.AVAILABLE
    assignment.vehicle.save(update_fields=["status"])


@transaction.atomic
def assign_shipment(*, shipment, driver, vehicle, actor):
    shipment = Shipment.objects.select_for_update().get(pk=shipment.pk)
    membership = Membership.objects.filter(organization=shipment.organization, user=actor).first()
    if membership is None or not membership.can_dispatch:
        raise PermissionDenied("Only dispatchers can assign shipments.")
    if shipment.status not in [
        Shipment.Status.UNASSIGNED,
        Shipment.Status.ASSIGNED,
        Shipment.Status.FAILED,
    ]:
        raise ValidationError("This shipment can no longer be reassigned.")

    current = DispatchAssignment.objects.filter(shipment=shipment).first()
    current_driver_id = current.driver_id if current else None
    current_vehicle_id = current.vehicle_id if current else None
    current_driver = current.driver if current else None
    current_vehicle = current.vehicle if current else None
    if driver.status != DriverProfile.Status.AVAILABLE and driver.pk != current_driver_id:
        raise ValidationError({"driver": "Driver is not currently available."})
    if not driver.is_license_valid:
        raise ValidationError({"driver": "Driver license is expired."})
    if vehicle.status != Vehicle.Status.AVAILABLE and vehicle.pk != current_vehicle_id:
        raise ValidationError({"vehicle": "Vehicle is not currently available."})
    if vehicle.is_service_due:
        raise ValidationError({"vehicle": "Vehicle is due for service and cannot be dispatched."})

    assignment = current or DispatchAssignment(
        organization=shipment.organization,
        shipment=shipment,
    )
    assignment.driver = driver
    assignment.vehicle = vehicle
    assignment.assigned_by = actor
    assignment.full_clean()
    if current and current_driver_id != driver.pk:
        current_driver.status = DriverProfile.Status.AVAILABLE
        current_driver.save(update_fields=["status"])
    if current and current_vehicle_id != vehicle.pk:
        current_vehicle.status = Vehicle.Status.AVAILABLE
        current_vehicle.save(update_fields=["status"])
    assignment.save()

    driver.status = DriverProfile.Status.ON_ROUTE
    driver.save(update_fields=["status"])
    vehicle.status = Vehicle.Status.ON_ROUTE
    vehicle.save(update_fields=["status"])
    shipment.status = Shipment.Status.ASSIGNED
    shipment.failure_reason = ""
    shipment.delivered_at = None
    shipment.delivery_reference = ""
    shipment.proof_note = ""
    shipment.full_clean()
    shipment.save(
        update_fields=[
            "status",
            "failure_reason",
            "delivered_at",
            "delivery_reference",
            "proof_note",
            "updated_at",
        ]
    )
    ShipmentEvent.objects.create(
        organization=shipment.organization,
        shipment=shipment,
        actor=actor,
        status=shipment.status,
        message=f"Assigned to {driver} in {vehicle.registration}.",
    )
    return assignment


@transaction.atomic
def transition_shipment(
    *,
    shipment,
    target_status,
    actor,
    message="",
    delivery_reference="",
    proof_note="",
    failure_reason="",
    visible_to_customer=True,
):
    shipment = (
        Shipment.objects.select_for_update()
        .select_related("organization", "assignment__driver", "assignment__vehicle")
        .get(pk=shipment.pk)
    )
    membership = Membership.objects.filter(organization=shipment.organization, user=actor).first()
    if membership is None:
        raise PermissionDenied("You do not belong to this workspace.")
    if membership.role == Membership.Role.VIEWER:
        raise PermissionDenied("Viewer accounts cannot update shipments.")
    if membership.role == Membership.Role.DRIVER:
        assignment = getattr(shipment, "assignment", None)
        if assignment is None or assignment.driver.user_id != actor.pk:
            raise PermissionDenied("Drivers may only update their assigned shipments.")
    if target_status not in dict(Shipment.Status.choices):
        raise ValidationError({"status": "Unknown shipment status."})
    if target_status not in ALLOWED_TRANSITIONS.get(shipment.status, set()):
        raise ValidationError(
            {"status": f"Cannot move from {shipment.get_status_display()} to that status."}
        )
    if target_status == Shipment.Status.CANCELLED and not membership.can_dispatch:
        raise PermissionDenied("Only dispatchers can cancel shipments.")

    shipment.status = target_status
    if target_status == Shipment.Status.DELIVERED:
        shipment.delivered_at = timezone.now()
        shipment.delivery_reference = delivery_reference.strip()
        shipment.proof_note = proof_note.strip()
    elif target_status == Shipment.Status.FAILED:
        shipment.failure_reason = failure_reason.strip()
    shipment.full_clean()
    shipment.save()

    if target_status in [
        Shipment.Status.DELIVERED,
        Shipment.Status.FAILED,
        Shipment.Status.CANCELLED,
    ]:
        _release_assignment_resources(shipment)

    event = ShipmentEvent(
        organization=shipment.organization,
        shipment=shipment,
        actor=actor,
        status=target_status,
        message=message.strip() or f"Shipment marked {shipment.get_status_display().lower()}.",
        visible_to_customer=visible_to_customer,
    )
    event.full_clean()
    event.save()
    return shipment
