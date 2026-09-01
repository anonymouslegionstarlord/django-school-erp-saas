import json

from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .decorators import manager_required, workspace_required
from .forms import (
    AssignmentForm,
    CustomerForm,
    DriverCreateForm,
    ShipmentForm,
    SignupForm,
    TransitionForm,
    VehicleForm,
)
from .models import Customer, DriverProfile, Membership, Organization, Shipment, Vehicle
from .services import assign_shipment, transition_shipment


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "dispatch/landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your dispatch workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def _visible_shipments(request):
    shipments = Shipment.objects.filter(organization=request.organization)
    if request.membership.role == Membership.Role.DRIVER:
        shipments = shipments.filter(assignment__driver__user=request.user)
    return shipments.select_related("customer", "assignment__driver__user", "assignment__vehicle")


@workspace_required
def dashboard(request):
    shipments = _visible_shipments(request)
    active_statuses = [
        Shipment.Status.ASSIGNED,
        Shipment.Status.PICKED_UP,
        Shipment.Status.IN_TRANSIT,
    ]
    today = timezone.localdate()
    month_ago = timezone.now() - timezone.timedelta(days=30)
    delivered_recent = shipments.filter(
        status=Shipment.Status.DELIVERED, delivered_at__gte=month_ago
    )
    delivered_on_time = delivered_recent.filter(delivered_at__lte=F("delivery_deadline"))
    delivered_count = delivered_recent.count()
    metrics = {
        "awaiting_dispatch": shipments.filter(status=Shipment.Status.UNASSIGNED).count(),
        "active_routes": shipments.filter(status__in=active_statuses).count(),
        "due_today": shipments.filter(delivery_deadline__date=today)
        .exclude(status__in=[Shipment.Status.DELIVERED, Shipment.Status.CANCELLED])
        .count(),
        "overdue": sum(1 for item in shipments if item.is_overdue),
        "on_time_rate": round(delivered_on_time.count() / delivered_count * 100)
        if delivered_count
        else 100,
    }
    status_rows = []
    for status, label in Shipment.Status.choices:
        count = shipments.filter(status=status).count()
        status_rows.append({"status": status, "label": label, "count": count})
    fleet = Vehicle.objects.filter(organization=request.organization)
    fleet_metrics = {
        "available": fleet.filter(status=Vehicle.Status.AVAILABLE).count(),
        "on_route": fleet.filter(status=Vehicle.Status.ON_ROUTE).count(),
        "service_due": sum(1 for vehicle in fleet if vehicle.is_service_due),
        "available_capacity": fleet.filter(status=Vehicle.Status.AVAILABLE).aggregate(
            total=Sum("capacity_kg")
        )["total"]
        or 0,
    }
    context = {
        "metrics": metrics,
        "fleet_metrics": fleet_metrics,
        "status_rows": status_rows,
        "urgent_shipments": shipments.filter(priority=Shipment.Priority.URGENT).exclude(
            status__in=[Shipment.Status.DELIVERED, Shipment.Status.CANCELLED]
        )[:5],
        "recent_shipments": shipments.order_by("-updated_at")[:7],
        "active_assignments": shipments.filter(status__in=active_statuses)[:6],
    }
    return render(request, "dispatch/dashboard.html", context)


@workspace_required
def shipment_list(request):
    shipments = _visible_shipments(request)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    priority = request.GET.get("priority", "").strip()
    if query:
        shipments = shipments.filter(
            Q(tracking_code__icontains=query)
            | Q(customer__name__icontains=query)
            | Q(delivery_address__icontains=query)
        )
    if status in Shipment.Status.values:
        shipments = shipments.filter(status=status)
    if priority in Shipment.Priority.values:
        shipments = shipments.filter(priority=priority)
    return render(
        request,
        "dispatch/shipment_list.html",
        {
            "shipments": shipments,
            "query": query,
            "selected_status": status,
            "selected_priority": priority,
            "status_choices": Shipment.Status.choices,
            "priority_choices": Shipment.Priority.choices,
        },
    )


@manager_required
def shipment_create(request):
    form = ShipmentForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        shipment = form.save(commit=False)
        shipment.organization = request.organization
        shipment.created_by = request.user
        shipment.full_clean()
        shipment.save()
        messages.success(request, f"Shipment {shipment.tracking_code} created.")
        return redirect("shipment_detail", pk=shipment.pk)
    return render(
        request,
        "dispatch/form.html",
        {"form": form, "title": "Create shipment", "eyebrow": "Dispatch intake"},
    )


@workspace_required
def shipment_detail(request, pk):
    shipment = get_object_or_404(_visible_shipments(request), pk=pk)
    transition_form = TransitionForm(shipment=shipment, membership=request.membership)
    public_url = request.build_absolute_uri(
        f"/track/{request.organization.slug}/{shipment.tracking_code}/"
    )
    return render(
        request,
        "dispatch/shipment_detail.html",
        {
            "shipment": shipment,
            "events": shipment.events.select_related("actor"),
            "transition_form": transition_form,
            "public_url": public_url,
        },
    )


@manager_required
def shipment_assign(request, pk):
    shipment = get_object_or_404(
        Shipment.objects.select_related("customer", "assignment__driver", "assignment__vehicle"),
        pk=pk,
        organization=request.organization,
    )
    form = AssignmentForm(
        request.POST or None, organization=request.organization, shipment=shipment
    )
    if request.method == "POST" and form.is_valid():
        try:
            assign_shipment(
                shipment=shipment,
                driver=form.cleaned_data["driver"],
                vehicle=form.cleaned_data["vehicle"],
                actor=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"{shipment.tracking_code} is ready for dispatch.")
            return redirect("shipment_detail", pk=shipment.pk)
    return render(
        request,
        "dispatch/form.html",
        {
            "form": form,
            "title": f"Assign {shipment.tracking_code}",
            "eyebrow": "Driver and vehicle",
            "shipment": shipment,
        },
    )


@workspace_required
@require_POST
def shipment_transition(request, pk):
    shipment = get_object_or_404(_visible_shipments(request), pk=pk)
    form = TransitionForm(request.POST, shipment=shipment, membership=request.membership)
    if form.is_valid():
        try:
            transition_shipment(
                shipment=shipment,
                target_status=form.cleaned_data["status"],
                actor=request.user,
                message=form.cleaned_data["update_message"],
                delivery_reference=form.cleaned_data["delivery_reference"],
                proof_note=form.cleaned_data["proof_note"],
                failure_reason=form.cleaned_data["failure_reason"],
                visible_to_customer=form.cleaned_data["visible_to_customer"],
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Shipment status updated.")
            return redirect("shipment_detail", pk=shipment.pk)
    public_url = request.build_absolute_uri(
        f"/track/{request.organization.slug}/{shipment.tracking_code}/"
    )
    return render(
        request,
        "dispatch/shipment_detail.html",
        {
            "shipment": shipment,
            "events": shipment.events.select_related("actor"),
            "transition_form": form,
            "public_url": public_url,
        },
        status=400,
    )


@workspace_required
def customer_list(request):
    customers = Customer.objects.filter(organization=request.organization).annotate(
        shipment_count=Count("shipments")
    )
    return render(request, "dispatch/customer_list.html", {"customers": customers})


@manager_required
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save(commit=False)
        customer.organization = request.organization
        customer.full_clean()
        customer.save()
        messages.success(request, f"Customer {customer.name} added.")
        return redirect("customer_list")
    return render(
        request,
        "dispatch/form.html",
        {"form": form, "title": "Add customer", "eyebrow": "Delivery customer"},
    )


@workspace_required
def fleet_list(request):
    vehicles = Vehicle.objects.filter(organization=request.organization)
    drivers = DriverProfile.objects.filter(organization=request.organization).select_related("user")
    return render(request, "dispatch/fleet_list.html", {"vehicles": vehicles, "drivers": drivers})


@manager_required
def vehicle_create(request):
    form = VehicleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vehicle = form.save(commit=False)
        vehicle.organization = request.organization
        vehicle.full_clean()
        vehicle.save()
        messages.success(request, f"Vehicle {vehicle.registration} added.")
        return redirect("fleet_list")
    return render(
        request,
        "dispatch/form.html",
        {"form": form, "title": "Add vehicle", "eyebrow": "Fleet capacity"},
    )


@manager_required
def driver_create(request):
    form = DriverCreateForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        driver = form.save()
        messages.success(request, f"Driver {driver} can now sign in.")
        return redirect("fleet_list")
    return render(
        request,
        "dispatch/form.html",
        {"form": form, "title": "Invite driver", "eyebrow": "Fleet team"},
    )


@require_GET
def public_tracking(request, organization_slug, tracking_code):
    organization = get_object_or_404(Organization, slug=organization_slug)
    shipment = get_object_or_404(
        Shipment.objects.select_related("customer"),
        organization=organization,
        tracking_code__iexact=tracking_code,
    )
    events = shipment.events.filter(visible_to_customer=True)
    return render(
        request,
        "dispatch/public_tracking.html",
        {"shipment": shipment, "events": events, "organization": organization},
    )


def _shipment_payload(shipment):
    assignment = getattr(shipment, "assignment", None)
    return {
        "id": shipment.pk,
        "tracking_code": shipment.tracking_code,
        "customer": shipment.customer.name,
        "priority": shipment.priority,
        "status": shipment.status,
        "scheduled_pickup": shipment.scheduled_pickup.isoformat(),
        "delivery_deadline": shipment.delivery_deadline.isoformat(),
        "overdue": shipment.is_overdue,
        "assignment": {
            "driver": str(assignment.driver),
            "vehicle": assignment.vehicle.registration,
        }
        if assignment
        else None,
    }


@workspace_required
@require_GET
def api_summary(request):
    shipments = _visible_shipments(request)
    counts = {status: shipments.filter(status=status).count() for status in Shipment.Status.values}
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "role": request.membership.role,
            "shipments": counts,
            "overdue": sum(1 for shipment in shipments if shipment.is_overdue),
            "available_vehicles": Vehicle.objects.filter(
                organization=request.organization, status=Vehicle.Status.AVAILABLE
            ).count(),
        }
    )


@workspace_required
@require_GET
def api_shipments(request):
    shipments = _visible_shipments(request)
    status = request.GET.get("status", "")
    if status in Shipment.Status.values:
        shipments = shipments.filter(status=status)
    return JsonResponse({"results": [_shipment_payload(item) for item in shipments[:100]]})


@workspace_required
@require_GET
def api_fleet(request):
    vehicles = Vehicle.objects.filter(organization=request.organization)
    drivers = DriverProfile.objects.filter(organization=request.organization).select_related("user")
    return JsonResponse(
        {
            "vehicles": [
                {
                    "registration": vehicle.registration,
                    "name": vehicle.name,
                    "kind": vehicle.kind,
                    "status": vehicle.status,
                    "capacity_kg": str(vehicle.capacity_kg),
                    "service_due": vehicle.is_service_due,
                }
                for vehicle in vehicles
            ],
            "drivers": [
                {
                    "name": str(driver),
                    "status": driver.status,
                    "license_valid": driver.is_license_valid,
                }
                for driver in drivers
            ],
        }
    )


@workspace_required
@require_POST
def api_transition(request, pk):
    shipment = get_object_or_404(_visible_shipments(request), pk=pk)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    try:
        shipment = transition_shipment(
            shipment=shipment,
            target_status=payload.get("status", ""),
            actor=request.user,
            message=payload.get("message", ""),
            delivery_reference=payload.get("delivery_reference", ""),
            proof_note=payload.get("proof_note", ""),
            failure_reason=payload.get("failure_reason", ""),
            visible_to_customer=bool(payload.get("visible_to_customer", True)),
        )
    except PermissionDenied as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValidationError as exc:
        return JsonResponse(
            {"error": exc.message_dict if hasattr(exc, "message_dict") else exc.messages},
            status=400,
        )
    return JsonResponse(_shipment_payload(shipment))
