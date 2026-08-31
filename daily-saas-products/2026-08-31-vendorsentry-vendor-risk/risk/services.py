from .models import AssessmentControl

BASELINE_CONTROLS = [
    (
        AssessmentControl.Domain.SECURITY,
        "Does the vendor enforce multi-factor authentication for privileged access?",
        5,
    ),
    (
        AssessmentControl.Domain.SECURITY,
        "Are vulnerability scanning and security patching performed on a defined schedule?",
        4,
    ),
    (
        AssessmentControl.Domain.PRIVACY,
        "Is customer data encrypted in transit and at rest with managed key rotation?",
        5,
    ),
    (
        AssessmentControl.Domain.PRIVACY,
        "Are retention, deletion, and data-subprocessor obligations documented?",
        4,
    ),
    (
        AssessmentControl.Domain.RESILIENCE,
        "Are disaster recovery plans tested with documented recovery objectives?",
        4,
    ),
    (
        AssessmentControl.Domain.RESILIENCE,
        "Does the vendor maintain an incident notification and escalation process?",
        4,
    ),
    (
        AssessmentControl.Domain.COMPLIANCE,
        "Are current independent assurance reports or certifications available?",
        3,
    ),
    (
        AssessmentControl.Domain.GOVERNANCE,
        "Are security responsibilities and right-to-audit terms included in the contract?",
        3,
    ),
]


def create_baseline_controls(assessment):
    controls = []
    for index, (domain, question, weight) in enumerate(BASELINE_CONTROLS, start=1):
        control, _ = AssessmentControl.objects.get_or_create(
            assessment=assessment,
            question=question,
            defaults={
                "organization": assessment.organization,
                "domain": domain,
                "weight": weight,
                "sort_order": index,
            },
        )
        controls.append(control)
    return controls
