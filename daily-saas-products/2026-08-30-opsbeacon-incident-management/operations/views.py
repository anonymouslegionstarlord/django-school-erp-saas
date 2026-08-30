from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import (
    ActionItemForm,
    IncidentForm,
    IncidentUpdateForm,
    ResponderForm,
    ServiceForm,
    SignupForm,
)
from .models import (
    ActionItem,
    Incident,
    IncidentResponder,
    IncidentUpdate,
    Organization,
    Service,
)


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
        messages.success(request, "Your OpsBeacon command center is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def public_status(request, slug):
    organization = get_object_or_404(Organization, slug=slug, status_page_enabled=True)
    services = Service.objects.filter(organization=organization, public=True).select_related(
        "owner"
    )
    incidents = (
        Incident.objects.filter(
            organization=organization,
            updates__public=True,
        )
        .filter(
            Q(
                status__in=[
                    Incident.Status.INVESTIGATING,
                    Incident.Status.IDENTIFIED,
                    Incident.Status.MONITORING,
                ]
            )
            | Q(resolved_at__gte=timezone.now() - timedelta(days=30))
        )
        .select_related("service")
        .distinct()
    )
    incident_rows = [
        {
            "incident": incident,
            "updates": incident.updates.filter(public=True)[:8],
        }
        for incident in incidents
    ]
    all_operational = not services.exclude(status=Service.Status.OPERATIONAL).exists()
    return render(
        request,
        "operations/public_status.html",
        {
            "status_organization": organization,
            "services": services,
            "incident_rows": incident_rows,
            "all_operational": all_operational,
        },
    )


def recalculate_service_status(service):
    active = service.incidents.exclude(status=Incident.Status.RESOLVED)
    if active.filter(severity=Incident.Severity.SEV1).exists():
        status = Service.Status.MAJOR_OUTAGE
    elif active.filter(severity=Incident.Severity.SEV2).exists():
        status = Service.Status.PARTIAL_OUTAGE
    elif active.exists():
        status = Service.Status.DEGRADED
    elif service.status == Service.Status.MAINTENANCE:
        return service.status
    else:
        status = Service.Status.OPERATIONAL
    if service.status != status:
        service.status = status
        service.save(update_fields=["status", "updated_at"])
    return status


@workspace_required
def dashboard(request):
    incidents = Incident.objects.filter(organization=request.organization).select_related(
        "service", "commander"
    )
    active = incidents.exclude(status=Incident.Status.RESOLVED)
    resolved_recently = incidents.filter(
        status=Incident.Status.RESOLVED,
        resolved_at__gte=timezone.now() - timedelta(days=30),
    )
    durations = [incident.duration_minutes for incident in resolved_recently]
    mttr = round(sum(durations) / len(durations)) if durations else None
    context = {
        "service_count": Service.objects.filter(organization=request.organization).count(),
        "affected_services": Service.objects.filter(organization=request.organization)
        .exclude(status=Service.Status.OPERATIONAL)
        .count(),
        "active_count": active.count(),
        "critical_count": active.filter(
            severity__in=[Incident.Severity.SEV1, Incident.Severity.SEV2]
        ).count(),
        "resolved_count": resolved_recently.count(),
        "mttr": mttr,
        "sla_breaches": sum(1 for incident in active if incident.sla_breached),
        "active_incidents": active[:6],
        "services": Service.objects.filter(organization=request.organization)[:8],
        "recently_resolved": resolved_recently[:4],
    }
    return render(request, "operations/dashboard.html", context)


@workspace_required
def service_list(request):
    services = Service.objects.filter(organization=request.organization).select_related("owner")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if query:
        services = services.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if status in Service.Status.values:
        services = services.filter(status=status)
    return render(
        request,
        "operations/service_list.html",
        {
            "services": services,
            "query": query,
            "status": status,
            "statuses": Service.Status.choices,
        },
    )


@workspace_required
def service_create(request):
    if not request.membership.can_manage:
        return HttpResponseForbidden("Only owners and commanders can create services.")
    form = ServiceForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        service = form.save(commit=False)
        service.organization = request.organization
        service.full_clean()
        service.save()
        messages.success(request, "Service added to the reliability catalog.")
        return redirect("service_list")
    return render(request, "operations/service_form.html", {"form": form})


@workspace_required
def service_edit(request, pk):
    if not request.membership.can_manage:
        return HttpResponseForbidden("Only owners and commanders can edit services.")
    service = get_object_or_404(Service, pk=pk, organization=request.organization)
    form = ServiceForm(
        request.POST or None,
        instance=service,
        organization=request.organization,
    )
    if request.method == "POST" and form.is_valid():
        service = form.save(commit=False)
        service.full_clean()
        service.save()
        messages.success(request, "Service settings updated.")
        return redirect("service_list")
    return render(request, "operations/service_form.html", {"form": form, "service": service})


@workspace_required
def incident_list(request):
    incidents = Incident.objects.filter(organization=request.organization).select_related(
        "service", "commander"
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    severity = request.GET.get("severity", "")
    service_id = request.GET.get("service", "")
    if query:
        incidents = incidents.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(service__name__icontains=query)
        )
    if status in Incident.Status.values:
        incidents = incidents.filter(status=status)
    if severity in Incident.Severity.values:
        incidents = incidents.filter(severity=severity)
    if service_id.isdigit():
        incidents = incidents.filter(service_id=service_id)
    return render(
        request,
        "operations/incident_list.html",
        {
            "incidents": incidents,
            "query": query,
            "status": status,
            "severity": severity,
            "service_id": service_id,
            "statuses": Incident.Status.choices,
            "severities": Incident.Severity.choices,
            "services": Service.objects.filter(organization=request.organization),
        },
    )


@workspace_required
def incident_create(request):
    if not request.membership.can_respond:
        return HttpResponseForbidden("Viewer accounts cannot declare incidents.")
    form = IncidentForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            incident = form.save(commit=False)
            incident.organization = request.organization
            incident.created_by = request.user
            incident.status = Incident.Status.INVESTIGATING
            incident.full_clean()
            incident.save()
            IncidentResponder.objects.create(
                organization=request.organization,
                incident=incident,
                user=incident.commander,
                responsibility="Incident commander",
            )
            update = IncidentUpdate(
                organization=request.organization,
                incident=incident,
                author=request.user,
                message=incident.summary,
                status=incident.status,
                public=bool(incident.customer_impact.strip()),
            )
            update.full_clean()
            update.save()
            recalculate_service_status(incident.service)
        messages.success(request, f"{incident.reference} declared and response started.")
        return redirect("incident_detail", pk=incident.pk)
    return render(request, "operations/incident_form.html", {"form": form})


@workspace_required
def incident_detail(request, pk):
    incident = get_object_or_404(
        Incident.objects.select_related("service", "commander", "created_by"),
        pk=pk,
        organization=request.organization,
    )
    can_coordinate = request.membership.can_manage or incident.commander_id == request.user.id
    return render(
        request,
        "operations/incident_detail.html",
        {
            "incident": incident,
            "updates": incident.updates.select_related("author"),
            "responders": incident.responders.select_related("user"),
            "action_items": incident.action_items.select_related("owner"),
            "update_form": IncidentUpdateForm(incident=incident),
            "responder_form": ResponderForm(organization=request.organization, incident=incident),
            "action_form": ActionItemForm(organization=request.organization),
            "can_coordinate": can_coordinate,
        },
    )


@workspace_required
@require_POST
def incident_update(request, pk):
    incident = get_object_or_404(
        Incident.objects.select_related("service"),
        pk=pk,
        organization=request.organization,
    )
    if not request.membership.can_respond:
        return HttpResponseForbidden("Viewer accounts cannot update incidents.")
    if not incident.is_active:
        return HttpResponseForbidden("Resolved incidents are read-only.")
    form = IncidentUpdateForm(request.POST, incident=incident)
    if form.is_valid():
        with transaction.atomic():
            previous_status = incident.status
            incident.status = form.cleaned_data["status"]
            if incident.status == Incident.Status.RESOLVED:
                incident.resolution_summary = form.cleaned_data["resolution_summary"].strip()
                incident.resolved_at = timezone.now()
            incident.full_clean()
            incident.save(
                update_fields=[
                    "status",
                    "resolution_summary",
                    "resolved_at",
                    "updated_at",
                ]
            )
            update = IncidentUpdate(
                organization=request.organization,
                incident=incident,
                author=request.user,
                message=form.cleaned_data["message"],
                status=incident.status,
                public=form.cleaned_data["public"],
            )
            update.full_clean()
            update.save()
            recalculate_service_status(incident.service)
        if previous_status != incident.status:
            messages.success(
                request,
                f"Incident moved to {incident.get_status_display().lower()}.",
            )
        else:
            messages.success(request, "Timeline update posted.")
    else:
        error = next(iter(form.errors.values()))[0]
        messages.error(request, f"Update was not posted: {error}")
    return redirect("incident_detail", pk=pk)


@workspace_required
@require_POST
def incident_responder_add(request, pk):
    incident = get_object_or_404(Incident, pk=pk, organization=request.organization)
    allowed = request.membership.can_manage or incident.commander_id == request.user.id
    if not allowed:
        return HttpResponseForbidden("Only commanders can assign responders.")
    if not incident.is_active:
        return HttpResponseForbidden("Resolved incidents are read-only.")
    form = ResponderForm(
        request.POST,
        organization=request.organization,
        incident=incident,
    )
    if form.is_valid():
        responder = form.save(commit=False)
        responder.organization = request.organization
        responder.incident = incident
        responder.full_clean()
        responder.save()
        IncidentUpdate.objects.create(
            organization=request.organization,
            incident=incident,
            author=request.user,
            message=(
                f"{responder.user.get_full_name() or responder.user.username} joined response"
                + (f" as {responder.responsibility}" if responder.responsibility else "")
            ),
            status=incident.status,
            public=False,
        )
        messages.success(request, "Responder assigned.")
    else:
        messages.error(request, "Responder could not be assigned.")
    return redirect("incident_detail", pk=pk)


@workspace_required
@require_POST
def incident_action_add(request, pk):
    incident = get_object_or_404(Incident, pk=pk, organization=request.organization)
    if not request.membership.can_respond:
        return HttpResponseForbidden("Viewer accounts cannot add action items.")
    if not incident.is_active:
        return HttpResponseForbidden("Resolved incidents are read-only.")
    form = ActionItemForm(request.POST, organization=request.organization)
    if form.is_valid():
        action = form.save(commit=False)
        action.organization = request.organization
        action.incident = incident
        action.full_clean()
        action.save()
        IncidentUpdate.objects.create(
            organization=request.organization,
            incident=incident,
            author=request.user,
            message=f"Action item created: {action.title}",
            status=incident.status,
            public=False,
        )
        messages.success(request, "Follow-up action added.")
    else:
        messages.error(request, "Action item could not be added.")
    return redirect("incident_detail", pk=pk)


@workspace_required
@require_POST
def incident_action_toggle(request, incident_pk, pk):
    incident = get_object_or_404(Incident, pk=incident_pk, organization=request.organization)
    action = get_object_or_404(
        ActionItem,
        pk=pk,
        incident=incident,
        organization=request.organization,
    )
    if not incident.is_active:
        return HttpResponseForbidden("Resolved incidents are read-only.")
    allowed = (
        request.membership.can_manage
        or incident.commander_id == request.user.id
        or action.owner_id == request.user.id
    )
    if not allowed:
        return HttpResponseForbidden("Only the action owner or commander can update it.")
    action.status = (
        ActionItem.Status.COMPLETED
        if action.status == ActionItem.Status.OPEN
        else ActionItem.Status.OPEN
    )
    action.completed_at = timezone.now() if action.status == ActionItem.Status.COMPLETED else None
    action.save(update_fields=["status", "completed_at"])
    label = "completed" if action.status == ActionItem.Status.COMPLETED else "reopened"
    IncidentUpdate.objects.create(
        organization=request.organization,
        incident=incident,
        author=request.user,
        message=f"Action item {label}: {action.title}",
        status=incident.status,
        public=False,
    )
    messages.success(request, f"Action item {label}.")
    return redirect("incident_detail", pk=incident_pk)


@workspace_required
def api_summary(request):
    incidents = Incident.objects.filter(organization=request.organization)
    active = incidents.exclude(status=Incident.Status.RESOLVED)
    resolved = incidents.filter(
        status=Incident.Status.RESOLVED,
        resolved_at__gte=timezone.now() - timedelta(days=30),
    )
    durations = [incident.duration_minutes for incident in resolved]
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "role": request.membership.role,
            "services": Service.objects.filter(organization=request.organization).count(),
            "affected_services": Service.objects.filter(organization=request.organization)
            .exclude(status=Service.Status.OPERATIONAL)
            .count(),
            "active_incidents": active.count(),
            "critical_incidents": active.filter(
                severity__in=[Incident.Severity.SEV1, Incident.Severity.SEV2]
            ).count(),
            "resolved_last_30_days": resolved.count(),
            "mttr_minutes": (round(sum(durations) / len(durations)) if durations else None),
            "active_sla_breaches": sum(1 for incident in active if incident.sla_breached),
        }
    )


@workspace_required
def api_services(request):
    services = Service.objects.filter(organization=request.organization).select_related("owner")
    return JsonResponse(
        {
            "results": [
                {
                    "id": service.pk,
                    "name": service.name,
                    "slug": service.slug,
                    "status": service.status,
                    "owner": service.owner.username,
                    "public": service.public,
                    "active_incidents": service.incidents.exclude(
                        status=Incident.Status.RESOLVED
                    ).count(),
                }
                for service in services
            ]
        }
    )


@workspace_required
def api_incidents(request):
    incidents = Incident.objects.filter(organization=request.organization).select_related(
        "service", "commander"
    )
    status = request.GET.get("status", "")
    severity = request.GET.get("severity", "")
    if status in Incident.Status.values:
        incidents = incidents.filter(status=status)
    if severity in Incident.Severity.values:
        incidents = incidents.filter(severity=severity)
    return JsonResponse(
        {
            "results": [
                {
                    "id": incident.pk,
                    "reference": incident.reference,
                    "title": incident.title,
                    "service": incident.service.name,
                    "severity": incident.severity,
                    "status": incident.status,
                    "commander": incident.commander.username,
                    "started_at": incident.started_at,
                    "resolved_at": incident.resolved_at,
                    "duration_minutes": incident.duration_minutes,
                    "resolution_target_minutes": incident.resolution_target_minutes,
                    "sla_breached": incident.sla_breached,
                }
                for incident in incidents
            ]
        }
    )


@workspace_required
def api_incident_detail(request, pk):
    incident = get_object_or_404(
        Incident.objects.select_related("service", "commander"),
        pk=pk,
        organization=request.organization,
    )
    return JsonResponse(
        {
            "id": incident.pk,
            "reference": incident.reference,
            "title": incident.title,
            "service": incident.service.name,
            "severity": incident.severity,
            "status": incident.status,
            "summary": incident.summary,
            "customer_impact": incident.customer_impact,
            "resolution_summary": incident.resolution_summary,
            "commander": incident.commander.username,
            "duration_minutes": incident.duration_minutes,
            "responders": [
                {
                    "username": responder.user.username,
                    "responsibility": responder.responsibility,
                    "joined_at": responder.joined_at,
                }
                for responder in incident.responders.select_related("user")
            ],
            "updates": [
                {
                    "status": update.status,
                    "message": update.message,
                    "public": update.public,
                    "author": update.author.username,
                    "created_at": update.created_at,
                }
                for update in incident.updates.select_related("author")
            ],
            "actions": [
                {
                    "title": action.title,
                    "owner": action.owner.username,
                    "due_date": action.due_date,
                    "status": action.status,
                    "overdue": action.is_overdue,
                }
                for action in incident.action_items.select_related("owner")
            ],
        }
    )
