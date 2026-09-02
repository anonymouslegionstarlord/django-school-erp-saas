import secrets
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import ClaimEvent, Inspection, Membership, ReturnClaim

ALLOWED_TRANSITIONS = {
    ReturnClaim.Status.SUBMITTED: {ReturnClaim.Status.TRIAGE},
    ReturnClaim.Status.TRIAGE: {
        ReturnClaim.Status.APPROVED,
        ReturnClaim.Status.REJECTED,
    },
    ReturnClaim.Status.APPROVED: {ReturnClaim.Status.AWAITING_ITEM},
    ReturnClaim.Status.AWAITING_ITEM: {ReturnClaim.Status.RECEIVED},
    ReturnClaim.Status.RECEIVED: {ReturnClaim.Status.INSPECTING},
    ReturnClaim.Status.INSPECTING: {ReturnClaim.Status.RESOLVED},
    ReturnClaim.Status.RESOLVED: {ReturnClaim.Status.CLOSED},
    ReturnClaim.Status.REJECTED: set(),
    ReturnClaim.Status.CLOSED: set(),
}

SLA_HOURS = {
    ReturnClaim.Priority.LOW: 72,
    ReturnClaim.Priority.NORMAL: 48,
    ReturnClaim.Priority.HIGH: 24,
    ReturnClaim.Priority.URGENT: 4,
}


def sla_deadline(priority, start=None):
    return (start or timezone.now()) + timedelta(hours=SLA_HOURS[priority])


def generate_tracking_code(organization):
    date_fragment = timezone.localdate().strftime("%y%m%d")
    for _ in range(12):
        code = f"RMA-{date_fragment}-{secrets.token_hex(8).upper()}"
        if not ReturnClaim.objects.filter(organization=organization, tracking_code=code).exists():
            return code
    raise RuntimeError("Unable to generate a unique claim tracking code.")


def transition_choices(claim, membership):
    if not membership.can_manage:
        return []
    allowed = ALLOWED_TRANSITIONS.get(claim.status, set())
    return [
        (value, ReturnClaim.Status(value).label)
        for value in ReturnClaim.Status.values
        if value in allowed
    ]


@transaction.atomic
def transition_claim(
    *,
    claim,
    target_status,
    actor,
    message="",
    rejection_reason="",
    resolution="",
    resolution_summary="",
    resolution_amount=0,
    replacement_reference="",
    visible_to_customer=True,
):
    claim = (
        ReturnClaim.objects.select_for_update()
        .select_related("organization", "item__product")
        .get(pk=claim.pk)
    )
    membership = Membership.objects.filter(organization=claim.organization, user=actor).first()
    if membership is None or not membership.can_manage:
        raise PermissionDenied("Only claims managers can change claim decisions.")
    if target_status not in dict(ReturnClaim.Status.choices):
        raise ValidationError({"status": "Unknown claim status."})
    if target_status not in ALLOWED_TRANSITIONS.get(claim.status, set()):
        raise ValidationError(
            {"status": f"Cannot move from {claim.get_status_display()} to that status."}
        )
    if target_status == ReturnClaim.Status.RESOLVED:
        if not Inspection.objects.filter(claim=claim).exists():
            raise ValidationError({"status": "Record an inspection before resolving the claim."})
        claim.resolved_at = timezone.now()
        claim.resolution = resolution
        claim.resolution_summary = resolution_summary.strip()
        claim.resolution_amount = resolution_amount or 0
        claim.replacement_reference = replacement_reference.strip()
    elif target_status == ReturnClaim.Status.APPROVED:
        claim.approved_at = timezone.now()
        claim.rejection_reason = ""
        claim.rejected_at = None
    elif target_status == ReturnClaim.Status.REJECTED:
        claim.rejected_at = timezone.now()
        claim.rejection_reason = rejection_reason.strip()
    elif target_status == ReturnClaim.Status.CLOSED:
        claim.closed_at = timezone.now()

    claim.status = target_status
    claim.full_clean()
    claim.save()
    event = ClaimEvent(
        organization=claim.organization,
        claim=claim,
        actor=actor,
        status=target_status,
        message=message.strip() or f"Claim moved to {claim.get_status_display().lower()}.",
        visible_to_customer=visible_to_customer,
    )
    event.full_clean()
    event.save()
    return claim


@transaction.atomic
def record_inspection(
    *,
    claim,
    actor,
    condition,
    fault_confirmed,
    findings,
    recommendation,
    customer_update="",
    visible_to_customer=True,
):
    claim = ReturnClaim.objects.select_for_update().get(pk=claim.pk)
    membership = Membership.objects.filter(organization=claim.organization, user=actor).first()
    if membership is None or not membership.can_inspect:
        raise PermissionDenied("Inspection access is required.")
    if claim.status not in [ReturnClaim.Status.RECEIVED, ReturnClaim.Status.INSPECTING]:
        raise ValidationError("Only received items can be inspected.")
    inspection = Inspection.objects.filter(claim=claim).first() or Inspection(
        organization=claim.organization,
        claim=claim,
    )
    inspection.technician = actor
    inspection.condition = condition
    inspection.fault_confirmed = fault_confirmed
    inspection.findings = findings.strip()
    inspection.recommendation = recommendation
    inspection.full_clean()
    inspection.save()

    claim.status = ReturnClaim.Status.INSPECTING
    claim.full_clean()
    claim.save(update_fields=["status", "updated_at"])
    ClaimEvent.objects.create(
        organization=claim.organization,
        claim=claim,
        actor=actor,
        status=claim.status,
        message=customer_update.strip() or "The returned item has been inspected.",
        visible_to_customer=visible_to_customer,
    )
    return inspection
