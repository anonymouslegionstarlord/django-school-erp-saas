import json

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ControlAreaForm, RequestForm, SignupForm, TaskForm
from .models import AuditFinding, RemediationTask
from .services import transition_finding, update_task


def workspace(request):
    membership = getattr(request.user, "audit_membership", None)
    if not membership:
        raise PermissionDenied
    return membership


def landing(request):
    return redirect("dashboard") if request.user.is_authenticated else render(request, "audit/landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("dashboard")
    return render(request, "audit/form.html", {"form": form, "title": "Create your workspace", "submit": "Start free"})


@login_required
def dashboard(request):
    membership = workspace(request)
    qs = AuditFinding.objects.filter(organization=membership.organization).select_related("control_area", "assigned_to")
    return render(
        request,
        "audit/dashboard.html",
        {
            "findings": qs[:8],
            "total": qs.count(),
            "overdue": sum(item.is_overdue for item in qs),
            "open_count": qs.exclude(status__in=[AuditFinding.Status.RESOLVED, AuditFinding.Status.ACCEPTED_RISK]).count(),
            "by_status": qs.values("status").annotate(total=Count("id")).order_by("status"),
        },
    )


@login_required
def finding_list(request):
    membership = workspace(request)
    qs = AuditFinding.objects.filter(organization=membership.organization).select_related("control_area", "assigned_to")
    query, status = request.GET.get("q", "").strip(), request.GET.get("status", "")
    if query:
        qs = qs.filter(Q(tracking_code__icontains=query) | Q(control_area__name__icontains=query) | Q(control_area__email__icontains=query))
    if status in AuditFinding.Status.values:
        qs = qs.filter(status=status)
    return render(
        request,
        "audit/finding_list.html",
        {"findings": qs, "query": query, "selected_status": status, "statuses": AuditFinding.Status.choices},
    )


@login_required
def finding_create(request):
    membership = workspace(request)
    if not membership.can_work:
        raise PermissionDenied
    draft = AuditFinding(organization=membership.organization, created_by=request.user)
    form = RequestForm(
        request.POST or None,
        organization=membership.organization,
        instance=draft,
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.organization, item.created_by = membership.organization, request.user
        item.full_clean()
        item.save()
        messages.success(request, "Audit finding created.")
        return redirect("finding_detail", pk=item.pk)
    return render(request, "audit/form.html", {"form": form, "title": "Log audit finding", "submit": "Create finding"})


@login_required
def finding_detail(request, pk):
    membership = workspace(request)
    item = get_object_or_404(
        AuditFinding.objects.select_related("control_area", "assigned_to"), pk=pk, organization=membership.organization
    )
    return render(
        request,
        "audit/finding_detail.html",
        {
            "item": item,
            "task_form": TaskForm(organization=membership.organization),
            "statuses": AuditFinding.Status.choices,
            "task_statuses": RemediationTask.Status.choices,
            "can_work": membership.can_work,
            "can_manage": membership.can_manage,
        },
    )


@login_required
def control_area_list(request):
    membership = workspace(request)
    form = ControlAreaForm(request.POST or None)
    if request.method == "POST":
        if not membership.can_work:
            raise PermissionDenied
        if form.is_valid():
            control_area = form.save(commit=False)
            control_area.organization = membership.organization
            control_area.save()
            messages.success(request, "Data control_area added.")
            return redirect("control_area_list")
    return render(
        request,
        "audit/control_area_list.html",
        {"control_areas": membership.organization.control_areas.all(), "form": form, "can_work": membership.can_work},
    )


@login_required
@require_POST
def task_create(request, pk):
    membership = workspace(request)
    if not membership.can_work:
        raise PermissionDenied
    item = get_object_or_404(AuditFinding, pk=pk, organization=membership.organization)
    form = TaskForm(
        request.POST,
        organization=membership.organization,
        instance=RemediationTask(finding=item),
    )
    if form.is_valid():
        task = form.save(commit=False)
        task.finding = item
        task.full_clean()
        task.save()
        messages.success(request, "Task added.")
    else:
        messages.error(request, "Please correct the task details.")
    return redirect("finding_detail", pk=pk)


@login_required
@require_POST
def transition(request, pk):
    try:
        transition_finding(
            pk, request.user, request.POST.get("status", ""), request.POST.get("note", ""), request.POST.get("evidence_reference", "")
        )
        messages.success(request, "Workflow updated.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else "You cannot perform that action.")
    return redirect("finding_detail", pk=pk)


@login_required
@require_POST
def task_update(request, pk):
    membership = workspace(request)
    task = get_object_or_404(RemediationTask.objects.select_related("finding"), pk=pk, finding__organization=membership.organization)
    try:
        update_task(task, request.user, request.POST.get("status", ""), request.POST.get("notes", ""))
        messages.success(request, "Task updated.")
    except (ValidationError, PermissionDenied):
        raise PermissionDenied from None
    return redirect("finding_detail", pk=task.finding_id)


def public_tracking(request, code):
    item = get_object_or_404(AuditFinding.objects.select_related("control_area"), tracking_code=code)
    return render(request, "audit/public_tracking.html", {"item": item, "events": item.events.filter(visible_to_stakeholders=True)})


@login_required
def api_findings(request):
    membership = workspace(request)
    qs = AuditFinding.objects.filter(organization=membership.organization).select_related("control_area")
    return JsonResponse(
        {
            "results": [
                {
                    "id": x.id,
                    "tracking_code": x.tracking_code,
                    "control_area": x.control_area.name,
                    "type": x.kind,
                    "status": x.status,
                    "due_at": x.due_at.isoformat(),
                    "overdue": x.is_overdue,
                }
                for x in qs
            ]
        }
    )


@login_required
@require_POST
def api_transition(request, pk):
    try:
        payload = json.loads(request.body or "{}")
        item = transition_finding(
            pk, request.user, payload.get("status", ""), payload.get("note", ""), payload.get("evidence_reference", "")
        )
        return JsonResponse({"id": item.id, "status": item.status})
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    except AuditFinding.DoesNotExist:
        return JsonResponse({"error": "Not found."}, status=404)
    except PermissionDenied:
        return JsonResponse({"error": "Forbidden."}, status=403)
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
