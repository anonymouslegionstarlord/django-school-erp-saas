from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import (
    AssessmentForm,
    ControlResponseForm,
    FindingForm,
    FindingStatusForm,
    SignupForm,
    VendorForm,
)
from .models import Activity, Assessment, AssessmentControl, Finding, Vendor
from .services import create_baseline_controls


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your VendorSentry risk workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def record_activity(*, organization, actor, vendor, message, assessment=None):
    activity = Activity(
        organization=organization,
        actor=actor,
        vendor=vendor,
        assessment=assessment,
        message=message,
    )
    activity.full_clean()
    activity.save()
    return activity


@workspace_required
def dashboard(request):
    vendors = Vendor.objects.filter(organization=request.organization).select_related(
        "business_owner"
    )
    assessments = Assessment.objects.filter(organization=request.organization).select_related(
        "vendor", "assessor"
    )
    findings = Finding.objects.filter(organization=request.organization).select_related(
        "vendor", "owner"
    )
    completed = list(assessments.filter(status=Assessment.Status.COMPLETED))
    scores = [assessment.score for assessment in completed if assessment.score is not None]
    vendor_rows = list(vendors)
    context = {
        "vendor_count": len(vendor_rows),
        "critical_vendor_count": sum(
            1
            for vendor in vendor_rows
            if vendor.criticality == Vendor.Criticality.CRITICAL or vendor.risk_rating == "critical"
        ),
        "review_due_count": sum(
            1
            for vendor in vendor_rows
            if vendor.next_review
            and vendor.next_review <= timezone.localdate() + timedelta(days=30)
            and vendor.status != Vendor.Status.OFFBOARDED
        ),
        "open_finding_count": findings.exclude(
            status__in=[Finding.Status.RESOLVED, Finding.Status.ACCEPTED]
        ).count(),
        "overdue_finding_count": sum(1 for finding in findings if finding.is_overdue),
        "average_score": round(sum(scores) / len(scores)) if scores else None,
        "annual_spend": vendors.aggregate(total=Sum("annual_spend"))["total"] or 0,
        "high_risk_vendors": [
            vendor
            for vendor in vendor_rows
            if vendor.risk_rating in ["critical", "high"]
            or vendor.criticality == Vendor.Criticality.CRITICAL
        ][:6],
        "due_assessments": assessments.exclude(status=Assessment.Status.COMPLETED).order_by(
            "due_date"
        )[:6],
        "open_findings": findings.exclude(
            status__in=[Finding.Status.RESOLVED, Finding.Status.ACCEPTED]
        )[:6],
        "recent_activity": Activity.objects.filter(
            organization=request.organization
        ).select_related("actor", "vendor")[:8],
    }
    return render(request, "risk/dashboard.html", context)


@workspace_required
def vendor_list(request):
    vendors = Vendor.objects.filter(organization=request.organization).select_related(
        "business_owner"
    )
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    criticality = request.GET.get("criticality", "")
    status = request.GET.get("status", "")
    if query:
        vendors = vendors.filter(
            Q(name__icontains=query)
            | Q(service_description__icontains=query)
            | Q(business_owner__username__icontains=query)
        )
    if category in Vendor.Category.values:
        vendors = vendors.filter(category=category)
    if criticality in Vendor.Criticality.values:
        vendors = vendors.filter(criticality=criticality)
    if status in Vendor.Status.values:
        vendors = vendors.filter(status=status)
    return render(
        request,
        "risk/vendor_list.html",
        {
            "vendors": vendors,
            "query": query,
            "category": category,
            "criticality": criticality,
            "status": status,
            "categories": Vendor.Category.choices,
            "criticalities": Vendor.Criticality.choices,
            "statuses": Vendor.Status.choices,
        },
    )


@workspace_required
def vendor_create(request):
    if not request.membership.can_manage:
        return HttpResponseForbidden("Only owners and risk managers can add vendors.")
    form = VendorForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        vendor = form.save(commit=False)
        vendor.organization = request.organization
        vendor.full_clean()
        vendor.save()
        record_activity(
            organization=request.organization,
            actor=request.user,
            vendor=vendor,
            message="Vendor added to the third-party register.",
        )
        messages.success(request, f"{vendor.name} added to the vendor register.")
        return redirect("vendor_detail", pk=vendor.pk)
    return render(request, "risk/vendor_form.html", {"form": form})


@workspace_required
def vendor_edit(request, pk):
    if not request.membership.can_manage:
        return HttpResponseForbidden("Only owners and risk managers can edit vendors.")
    vendor = get_object_or_404(Vendor, pk=pk, organization=request.organization)
    form = VendorForm(request.POST or None, instance=vendor, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        vendor = form.save(commit=False)
        vendor.full_clean()
        vendor.save()
        record_activity(
            organization=request.organization,
            actor=request.user,
            vendor=vendor,
            message="Vendor profile and exposure details updated.",
        )
        messages.success(request, "Vendor profile updated.")
        return redirect("vendor_detail", pk=vendor.pk)
    return render(request, "risk/vendor_form.html", {"form": form, "vendor": vendor})


@workspace_required
def vendor_detail(request, pk):
    vendor = get_object_or_404(
        Vendor.objects.select_related("business_owner"),
        pk=pk,
        organization=request.organization,
    )
    assessments = vendor.assessments.select_related("assessor")
    findings = vendor.findings.select_related("owner", "assessment")
    return render(
        request,
        "risk/vendor_detail.html",
        {
            "vendor": vendor,
            "assessments": assessments,
            "findings": findings,
            "activity": vendor.activity.select_related("actor")[:10],
        },
    )


@workspace_required
def assessment_list(request):
    assessments = Assessment.objects.filter(organization=request.organization).select_related(
        "vendor", "assessor"
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    vendor_id = request.GET.get("vendor", "")
    if query:
        assessments = assessments.filter(
            Q(title__icontains=query) | Q(scope__icontains=query) | Q(vendor__name__icontains=query)
        )
    if status in Assessment.Status.values:
        assessments = assessments.filter(status=status)
    if vendor_id.isdigit():
        assessments = assessments.filter(vendor_id=vendor_id)
    return render(
        request,
        "risk/assessment_list.html",
        {
            "assessments": assessments,
            "query": query,
            "status": status,
            "vendor_id": vendor_id,
            "statuses": Assessment.Status.choices,
            "vendors": Vendor.objects.filter(organization=request.organization),
        },
    )


@workspace_required
def assessment_create(request):
    if not request.membership.can_assess:
        return HttpResponseForbidden("Viewer accounts cannot create assessments.")
    requested_vendor = None
    vendor_id = request.GET.get("vendor", "")
    if vendor_id.isdigit():
        requested_vendor = get_object_or_404(
            Vendor, pk=vendor_id, organization=request.organization
        )
    form = AssessmentForm(
        request.POST or None,
        organization=request.organization,
        vendor=requested_vendor,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            assessment = form.save(commit=False)
            assessment.organization = request.organization
            assessment.full_clean()
            assessment.save()
            create_baseline_controls(assessment)
            if assessment.vendor.status == Vendor.Status.ONBOARDING:
                assessment.vendor.status = Vendor.Status.UNDER_REVIEW
                assessment.vendor.save(update_fields=["status", "updated_at"])
            record_activity(
                organization=request.organization,
                actor=request.user,
                vendor=assessment.vendor,
                assessment=assessment,
                message=f"Assessment started: {assessment.title}",
            )
        messages.success(request, "Assessment created with the baseline control set.")
        return redirect("assessment_detail", pk=assessment.pk)
    return render(request, "risk/assessment_form.html", {"form": form})


@workspace_required
def assessment_detail(request, pk):
    assessment = get_object_or_404(
        Assessment.objects.select_related("vendor", "assessor"),
        pk=pk,
        organization=request.organization,
    )
    control_rows = [
        {"control": control, "form": ControlResponseForm(instance=control)}
        for control in assessment.controls.all()
    ]
    findings = assessment.findings.select_related("owner")
    can_coordinate = request.membership.can_manage or assessment.assessor_id == request.user.id
    return render(
        request,
        "risk/assessment_detail.html",
        {
            "assessment": assessment,
            "control_rows": control_rows,
            "findings": findings,
            "finding_form": FindingForm(organization=request.organization),
            "finding_statuses": Finding.Status.choices,
            "can_coordinate": can_coordinate,
        },
    )


@workspace_required
@require_POST
def control_update(request, assessment_pk, pk):
    assessment = get_object_or_404(Assessment, pk=assessment_pk, organization=request.organization)
    control = get_object_or_404(
        AssessmentControl,
        pk=pk,
        assessment=assessment,
        organization=request.organization,
    )
    allowed = request.membership.can_manage or assessment.assessor_id == request.user.id
    if not allowed:
        return HttpResponseForbidden("Only the assessor or risk manager can score controls.")
    if assessment.status == Assessment.Status.COMPLETED:
        return HttpResponseForbidden("Completed assessments are read-only.")
    form = ControlResponseForm(request.POST, instance=control)
    if form.is_valid():
        control = form.save(commit=False)
        control.full_clean()
        control.save()
        messages.success(request, "Control response saved.")
    else:
        messages.error(request, "Control response could not be saved.")
    return redirect("assessment_detail", pk=assessment.pk)


@workspace_required
@require_POST
def assessment_transition(request, pk):
    assessment = get_object_or_404(
        Assessment.objects.select_related("vendor"),
        pk=pk,
        organization=request.organization,
    )
    allowed = request.membership.can_manage or assessment.assessor_id == request.user.id
    if not allowed:
        return HttpResponseForbidden(
            "Only the assessor or risk manager can transition this review."
        )
    if assessment.status == Assessment.Status.COMPLETED:
        return HttpResponseForbidden("Completed assessments are read-only.")
    action = request.POST.get("action")
    if action == "review":
        assessment.status = Assessment.Status.IN_REVIEW
        assessment.save(update_fields=["status", "updated_at"])
        record_activity(
            organization=request.organization,
            actor=request.user,
            vendor=assessment.vendor,
            assessment=assessment,
            message=f"Assessment moved to review at {assessment.progress_percent}% complete.",
        )
        messages.success(request, "Assessment moved to review.")
    elif action == "complete":
        if assessment.controls.filter(response=AssessmentControl.Response.UNANSWERED).exists():
            messages.error(request, "Answer every control before completing the assessment.")
            return redirect("assessment_detail", pk=assessment.pk)
        with transaction.atomic():
            assessment.status = Assessment.Status.COMPLETED
            assessment.completed_at = timezone.now()
            assessment.full_clean()
            assessment.save(update_fields=["status", "completed_at", "updated_at"])
            assessment.vendor.status = Vendor.Status.ACTIVE
            assessment.vendor.next_review = timezone.localdate() + timedelta(days=365)
            assessment.vendor.save(update_fields=["status", "next_review", "updated_at"])
            record_activity(
                organization=request.organization,
                actor=request.user,
                vendor=assessment.vendor,
                assessment=assessment,
                message=(
                    f"Assessment completed with {assessment.score}% residual risk "
                    f"({assessment.risk_rating})."
                ),
            )
        messages.success(request, "Assessment completed and next review scheduled.")
    else:
        return HttpResponseBadRequest("Unknown assessment action.")
    return redirect("assessment_detail", pk=assessment.pk)


@workspace_required
@require_POST
def finding_add(request, assessment_pk):
    assessment = get_object_or_404(
        Assessment.objects.select_related("vendor"),
        pk=assessment_pk,
        organization=request.organization,
    )
    if not request.membership.can_assess:
        return HttpResponseForbidden("Viewer accounts cannot create findings.")
    form = FindingForm(request.POST, organization=request.organization)
    if form.is_valid():
        finding = form.save(commit=False)
        finding.organization = request.organization
        finding.vendor = assessment.vendor
        finding.assessment = assessment
        finding.full_clean()
        finding.save()
        record_activity(
            organization=request.organization,
            actor=request.user,
            vendor=assessment.vendor,
            assessment=assessment,
            message=f"{finding.get_severity_display()} finding opened: {finding.title}",
        )
        messages.success(request, "Remediation finding added.")
    else:
        messages.error(request, "Finding could not be added.")
    return redirect("assessment_detail", pk=assessment.pk)


@workspace_required
@require_POST
def finding_update(request, pk):
    finding = get_object_or_404(
        Finding.objects.select_related("assessment", "vendor"),
        pk=pk,
        organization=request.organization,
    )
    allowed = request.membership.can_manage or finding.owner_id == request.user.id
    if not allowed:
        return HttpResponseForbidden("Only the finding owner or risk manager can update it.")
    form = FindingStatusForm(request.POST)
    if form.is_valid():
        finding.status = form.cleaned_data["status"]
        finding.resolution_notes = form.cleaned_data["resolution_notes"].strip()
        finding.resolved_at = timezone.now() if finding.status == Finding.Status.RESOLVED else None
        finding.full_clean()
        finding.save(update_fields=["status", "resolution_notes", "resolved_at", "updated_at"])
        record_activity(
            organization=request.organization,
            actor=request.user,
            vendor=finding.vendor,
            assessment=finding.assessment,
            message=f"Finding moved to {finding.get_status_display().lower()}: {finding.title}",
        )
        messages.success(request, "Finding status updated.")
    else:
        error = next(iter(form.errors.values()))[0]
        messages.error(request, f"Finding was not updated: {error}")
    return redirect("assessment_detail", pk=finding.assessment_id)


@workspace_required
def api_summary(request):
    vendors = list(Vendor.objects.filter(organization=request.organization))
    assessments = Assessment.objects.filter(organization=request.organization)
    findings = Finding.objects.filter(organization=request.organization)
    completed = list(assessments.filter(status=Assessment.Status.COMPLETED))
    scores = [assessment.score for assessment in completed if assessment.score is not None]
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "role": request.membership.role,
            "vendors": len(vendors),
            "high_or_critical_risk_vendors": sum(
                1 for vendor in vendors if vendor.risk_rating in ["high", "critical"]
            ),
            "assessments_in_progress": assessments.exclude(
                status=Assessment.Status.COMPLETED
            ).count(),
            "average_residual_risk": (round(sum(scores) / len(scores)) if scores else None),
            "open_findings": findings.exclude(
                status__in=[Finding.Status.RESOLVED, Finding.Status.ACCEPTED]
            ).count(),
            "overdue_findings": sum(1 for finding in findings if finding.is_overdue),
        }
    )


@workspace_required
def api_vendors(request):
    vendors = Vendor.objects.filter(organization=request.organization).select_related(
        "business_owner"
    )
    return JsonResponse(
        {
            "results": [
                {
                    "id": vendor.pk,
                    "name": vendor.name,
                    "category": vendor.category,
                    "criticality": vendor.criticality,
                    "status": vendor.status,
                    "risk_rating": vendor.risk_rating,
                    "business_owner": vendor.business_owner.username,
                    "exposure_count": vendor.exposure_count,
                    "annual_spend": str(vendor.annual_spend),
                    "next_review": vendor.next_review,
                    "review_due": vendor.is_review_due,
                }
                for vendor in vendors
            ]
        }
    )


@workspace_required
def api_assessments(request):
    assessments = Assessment.objects.filter(organization=request.organization).select_related(
        "vendor", "assessor"
    )
    status = request.GET.get("status", "")
    if status in Assessment.Status.values:
        assessments = assessments.filter(status=status)
    return JsonResponse(
        {
            "results": [
                {
                    "id": assessment.pk,
                    "vendor": assessment.vendor.name,
                    "title": assessment.title,
                    "assessor": assessment.assessor.username,
                    "status": assessment.status,
                    "due_date": assessment.due_date,
                    "progress_percent": assessment.progress_percent,
                    "score": assessment.score,
                    "risk_rating": assessment.risk_rating,
                    "overdue": assessment.is_overdue,
                }
                for assessment in assessments
            ]
        }
    )


@workspace_required
def api_findings(request):
    findings = Finding.objects.filter(organization=request.organization).select_related(
        "vendor", "assessment", "owner"
    )
    status = request.GET.get("status", "")
    severity = request.GET.get("severity", "")
    if status in Finding.Status.values:
        findings = findings.filter(status=status)
    if severity in Finding.Severity.values:
        findings = findings.filter(severity=severity)
    return JsonResponse(
        {
            "results": [
                {
                    "id": finding.pk,
                    "vendor": finding.vendor.name,
                    "assessment_id": finding.assessment_id,
                    "title": finding.title,
                    "severity": finding.severity,
                    "owner": finding.owner.username,
                    "status": finding.status,
                    "due_date": finding.due_date,
                    "overdue": finding.is_overdue,
                }
                for finding in findings
            ]
        }
    )
