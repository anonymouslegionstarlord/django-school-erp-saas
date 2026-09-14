from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AuditFinding, FindingEvent, RemediationTask

TRANSITIONS = {
    AuditFinding.Status.OPEN: [AuditFinding.Status.TRIAGE],
    AuditFinding.Status.TRIAGE: [AuditFinding.Status.REMEDIATION, AuditFinding.Status.ACCEPTED_RISK],
    AuditFinding.Status.REMEDIATION: [AuditFinding.Status.REVIEW],
    AuditFinding.Status.REVIEW: [AuditFinding.Status.REMEDIATION, AuditFinding.Status.RESOLVED, AuditFinding.Status.ACCEPTED_RISK],
}


@transaction.atomic
def transition_finding(finding_id, actor, target, note="", evidence_reference=""):
    item = AuditFinding.objects.select_for_update().get(pk=finding_id)
    membership = getattr(actor, "audit_membership", None)
    if not membership or membership.organization_id != item.organization_id or not membership.can_work:
        raise PermissionDenied
    if target not in TRANSITIONS.get(item.status, []):
        raise ValidationError("That workflow transition is not allowed.")
    if target in {AuditFinding.Status.ACCEPTED_RISK, AuditFinding.Status.RESOLVED} and not membership.can_manage:
        raise PermissionDenied
    if target == AuditFinding.Status.REMEDIATION and item.status == AuditFinding.Status.TRIAGE:
        item.triaged_at = timezone.now()
    if target == AuditFinding.Status.REVIEW and (
        not item.tasks.exists() or item.tasks.exclude(status=RemediationTask.Status.DONE).exists()
    ):
        raise ValidationError("Complete every finding task before final review.")
    if target == AuditFinding.Status.ACCEPTED_RISK:
        if not note.strip():
            raise ValidationError("Provide a documented risk-acceptance reason.")
        item.risk_acceptance_reason = note.strip()
        item.completed_at = timezone.now()
    if target == AuditFinding.Status.RESOLVED:
        if not note.strip() or not evidence_reference.strip():
            raise ValidationError("Provide a resolution summary and evidence reference.")
        item.resolution_summary = note.strip()
        item.evidence_reference = evidence_reference.strip()
        item.completed_at = timezone.now()
    item.status = target
    item.full_clean()
    item.save()
    FindingEvent.objects.create(
        finding=item,
        actor=actor,
        message=note.strip() or f"Status changed to {item.get_status_display()}.",
        visible_to_stakeholders=target in {AuditFinding.Status.RESOLVED, AuditFinding.Status.ACCEPTED_RISK},
    )
    return item


def update_task(task, actor, status, notes=""):
    membership = getattr(actor, "audit_membership", None)
    if not membership or membership.organization_id != task.finding.organization_id:
        raise PermissionDenied
    if task.assignee_id != actor.id and not membership.can_manage:
        raise PermissionDenied
    if status not in RemediationTask.Status.values:
        raise ValidationError("Invalid task status.")
    task.status = status
    task.notes = notes.strip()
    task.completed_at = timezone.now() if status == RemediationTask.Status.DONE else None
    task.save()
    return task
