from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import workspace_required
from .forms import AssetForm, SiteForm, SignupForm, WorkLogForm, WorkOrderForm, WorkOrderUpdateForm
from .models import Asset, Site, WorkOrder


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "maintenance/landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your MaintainIQ workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def visible_orders(request):
    rows = WorkOrder.objects.filter(organization=request.organization).select_related(
        "site", "asset", "assigned_to", "requested_by"
    )
    if not request.membership.can_manage:
        rows = rows.filter(requested_by=request.user)
    return rows


@workspace_required
def dashboard(request):
    orders = visible_orders(request)
    active = orders.exclude(status__in=[WorkOrder.Status.COMPLETED, WorkOrder.Status.CANCELLED])
    overdue = [order for order in active if order.is_overdue]
    context = {
        "open_count": active.count(),
        "critical_count": active.filter(priority=WorkOrder.Priority.CRITICAL).count(),
        "overdue_count": len(overdue),
        "completed_count": orders.filter(status=WorkOrder.Status.COMPLETED).count(),
        "urgent_orders": active.filter(
            Q(priority=WorkOrder.Priority.CRITICAL) | Q(priority=WorkOrder.Priority.HIGH)
        )[:6],
        "recent_orders": orders[:7],
        "asset_alerts": Asset.objects.filter(
            organization=request.organization,
            condition__in=[Asset.Condition.WATCH, Asset.Condition.DOWN],
        )[:6],
    }
    return render(request, "maintenance/dashboard.html", context)


@workspace_required
def work_orders(request):
    rows = visible_orders(request)
    status = request.GET.get("status", "")
    query = request.GET.get("q", "").strip()
    if status:
        rows = rows.filter(status=status)
    if query:
        rows = rows.filter(Q(number__icontains=query) | Q(title__icontains=query))
    return render(
        request,
        "maintenance/work_orders.html",
        {
            "orders": rows,
            "status": status,
            "query": query,
            "status_choices": WorkOrder.Status.choices,
        },
    )


@workspace_required
def create_work_order(request):
    form = WorkOrderForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        order = form.save(commit=False)
        order.organization = request.organization
        order.requested_by = request.user
        order.save()
        messages.success(request, "Work order created.")
        return redirect("work_order_detail", pk=order.pk)
    return render(request, "maintenance/work_order_form.html", {"form": form})


@workspace_required
def work_order_detail(request, pk):
    order = get_object_or_404(visible_orders(request).prefetch_related("logs__author"), pk=pk)
    update_form = WorkOrderUpdateForm(
        request.POST or None,
        instance=order,
        organization=request.organization,
        prefix="update",
    )
    log_form = WorkLogForm(request.POST or None, prefix="log")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update" and request.membership.can_manage and update_form.is_valid():
            updated = update_form.save(commit=False)
            if updated.status == WorkOrder.Status.COMPLETED and not updated.completed_at:
                updated.completed_at = timezone.now()
            elif updated.status != WorkOrder.Status.COMPLETED:
                updated.completed_at = None
            updated.save()
            messages.success(request, "Work order updated.")
            return redirect("work_order_detail", pk=pk)
        if action == "log" and request.membership.can_manage and log_form.is_valid():
            log = log_form.save(commit=False)
            log.organization = request.organization
            log.work_order = order
            log.author = request.user
            log.save()
            messages.success(request, "Service log added.")
            return redirect("work_order_detail", pk=pk)
        if not request.membership.can_manage:
            messages.error(request, "Only owners and technicians can update maintenance work.")
    return render(
        request,
        "maintenance/work_order_detail.html",
        {"order": order, "update_form": update_form, "log_form": log_form},
    )


@workspace_required
def assets(request):
    form = AssetForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid() and request.membership.can_manage:
        asset = form.save(commit=False)
        asset.organization = request.organization
        asset.save()
        messages.success(request, "Asset added.")
        return redirect("assets")
    rows = Asset.objects.filter(organization=request.organization).select_related("site")
    return render(request, "maintenance/assets.html", {"assets": rows, "form": form})


@workspace_required
def sites(request):
    form = SiteForm(request.POST or None)
    if request.method == "POST" and form.is_valid() and request.membership.can_manage:
        site = form.save(commit=False)
        site.organization = request.organization
        site.save()
        messages.success(request, "Site added.")
        return redirect("sites")
    rows = Site.objects.filter(organization=request.organization)
    return render(request, "maintenance/sites.html", {"sites": rows, "form": form})


def order_payload(order):
    return {
        "id": order.id,
        "number": order.number,
        "title": order.title,
        "site": order.site.name,
        "asset": order.asset.name if order.asset else None,
        "priority": order.priority,
        "status": order.status,
        "due_at": order.due_at,
        "overdue": order.is_overdue,
    }


@workspace_required
def api_summary(request):
    orders = visible_orders(request)
    active = orders.exclude(status__in=[WorkOrder.Status.COMPLETED, WorkOrder.Status.CANCELLED])
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "active": active.count(),
            "overdue": sum(order.is_overdue for order in active),
            "critical": active.filter(priority=WorkOrder.Priority.CRITICAL).count(),
            "assets": Asset.objects.filter(organization=request.organization).count(),
        }
    )


@workspace_required
def api_work_orders(request):
    return JsonResponse({"results": [order_payload(order) for order in visible_orders(request)]})


@workspace_required
def api_assets(request):
    rows = Asset.objects.filter(organization=request.organization).select_related("site")
    return JsonResponse(
        {
            "results": [
                {
                    "id": asset.id,
                    "tag": asset.tag,
                    "name": asset.name,
                    "site": asset.site.name,
                    "condition": asset.condition,
                }
                for asset in rows
            ]
        }
    )
