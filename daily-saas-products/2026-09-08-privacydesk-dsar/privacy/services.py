from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import PrivacyRequest, RequestEvent, RequestTask

TRANSITIONS = {
    PrivacyRequest.Status.RECEIVED: [PrivacyRequest.Status.VERIFYING],
    PrivacyRequest.Status.VERIFYING: [PrivacyRequest.Status.IN_PROGRESS, PrivacyRequest.Status.REJECTED],
    PrivacyRequest.Status.IN_PROGRESS: [PrivacyRequest.Status.REVIEW],
    PrivacyRequest.Status.REVIEW: [PrivacyRequest.Status.IN_PROGRESS, PrivacyRequest.Status.FULFILLED, PrivacyRequest.Status.REJECTED],
}


@transaction.atomic
def transition_request(request_id, actor, target, note="", delivery_reference=""):
    item = PrivacyRequest.objects.select_for_update().get(pk=request_id)
    membership = getattr(actor, "privacy_membership", None)
    if not membership or membership.organization_id != item.organization_id or not membership.can_work:
        raise PermissionDenied
    if target not in TRANSITIONS.get(item.status, []):
        raise ValidationError("That workflow transition is not allowed.")
    if target in {PrivacyRequest.Status.REJECTED, PrivacyRequest.Status.FULFILLED} and not membership.can_manage:
        raise PermissionDenied
    if target == PrivacyRequest.Status.IN_PROGRESS and item.status == PrivacyRequest.Status.VERIFYING:
        item.identity_verified_at = timezone.now()
    if target == PrivacyRequest.Status.REVIEW and (not item.tasks.exists() or item.tasks.exclude(status=RequestTask.Status.DONE).exists()):
        raise ValidationError("Complete every request task before final review.")
    if target == PrivacyRequest.Status.REJECTED:
        if not note.strip():
            raise ValidationError("Provide a rejection reason.")
        item.rejection_reason = note.strip()
        item.completed_at = timezone.now()
    if target == PrivacyRequest.Status.FULFILLED:
        if not note.strip() or not delivery_reference.strip():
            raise ValidationError("Provide a resolution summary and secure delivery reference.")
        item.resolution_summary = note.strip()
        item.secure_delivery_reference = delivery_reference.strip()
        item.completed_at = timezone.now()
    item.status = target
    item.full_clean()
    item.save()
    RequestEvent.objects.create(
        request=item,
        actor=actor,
        message=note.strip() or f"Status changed to {item.get_status_display()}.",
        visible_to_subject=target in {PrivacyRequest.Status.FULFILLED, PrivacyRequest.Status.REJECTED},
    )
    return item


def update_task(task, actor, status, notes=""):
    membership = getattr(actor, "privacy_membership", None)
    if not membership or membership.organization_id != task.request.organization_id:
        raise PermissionDenied
    if task.assignee_id != actor.id and not membership.can_manage:
        raise PermissionDenied
    if status not in RequestTask.Status.values:
        raise ValidationError("Invalid task status.")
    task.status = status
    task.notes = notes.strip()
    task.completed_at = timezone.now() if status == RequestTask.Status.DONE else None
    task.save()
    return task
