import json

from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .decorators import inspector_required, manager_required, workspace_required
from .forms import (
    ClaimForm,
    CustomerForm,
    InspectionForm,
    ProductForm,
    RegisteredItemForm,
    SignupForm,
    TeamMemberForm,
    TransitionForm,
)
from .models import Customer, Membership, Product, RegisteredItem, ReturnClaim
from .services import (
    generate_tracking_code,
    record_inspection,
    sla_deadline,
    transition_claim,
)


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "returns/landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your returns workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def _claims(request):
    return ReturnClaim.objects.filter(organization=request.organization).select_related(
        "item__product", "item__customer", "inspection__technician"
    )


@workspace_required
def dashboard(request):
    claims = _claims(request)
    now = timezone.now()
    month_ago = now - timezone.timedelta(days=30)
    terminal = [ReturnClaim.Status.REJECTED, ReturnClaim.Status.CLOSED]
    resolved_recent = claims.filter(resolved_at__gte=month_ago)
    refund_total = (
        resolved_recent.filter(
            resolution__in=[
                ReturnClaim.Resolution.REFUNDED,
                ReturnClaim.Resolution.STORE_CREDIT,
            ]
        ).aggregate(total=Sum("resolution_amount"))["total"]
        or 0
    )
    metrics = {
        "open": claims.exclude(status__in=terminal).count(),
        "new": claims.filter(
            status__in=[ReturnClaim.Status.SUBMITTED, ReturnClaim.Status.TRIAGE]
        ).count(),
        "inspection_queue": claims.filter(
            status__in=[ReturnClaim.Status.RECEIVED, ReturnClaim.Status.INSPECTING]
        ).count(),
        "overdue": sum(1 for claim in claims if claim.is_overdue),
        "resolved_30d": resolved_recent.count(),
        "refund_total": refund_total,
    }
    status_rows = [
        {
            "status": status,
            "label": label,
            "count": claims.filter(status=status).count(),
        }
        for status, label in ReturnClaim.Status.choices
    ]
    return render(
        request,
        "returns/dashboard.html",
        {
            "metrics": metrics,
            "status_rows": status_rows,
            "overdue_claims": [claim for claim in claims if claim.is_overdue][:5],
            "recent_claims": claims.order_by("-updated_at")[:7],
            "inspection_claims": claims.filter(
                status__in=[ReturnClaim.Status.RECEIVED, ReturnClaim.Status.INSPECTING]
            )[:5],
        },
    )


@workspace_required
def claim_list(request):
    claims = _claims(request)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    priority = request.GET.get("priority", "").strip()
    if query:
        claims = claims.filter(
            Q(tracking_code__icontains=query)
            | Q(item__serial_number__icontains=query)
            | Q(item__product__name__icontains=query)
            | Q(item__customer__name__icontains=query)
        )
    if status in ReturnClaim.Status.values:
        claims = claims.filter(status=status)
    if priority in ReturnClaim.Priority.values:
        claims = claims.filter(priority=priority)
    return render(
        request,
        "returns/claim_list.html",
        {
            "claims": claims,
            "query": query,
            "selected_status": status,
            "selected_priority": priority,
            "status_choices": ReturnClaim.Status.choices,
            "priority_choices": ReturnClaim.Priority.choices,
        },
    )


@manager_required
def claim_create(request):
    form = ClaimForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        claim = form.save(commit=False)
        claim.organization = request.organization
        claim.created_by = request.user
        claim.tracking_code = generate_tracking_code(request.organization)
        claim.response_due = sla_deadline(claim.priority)
        claim.full_clean()
        claim.save()
        messages.success(request, f"Claim {claim.tracking_code} opened.")
        return redirect("claim_detail", pk=claim.pk)
    return render(
        request,
        "returns/form.html",
        {"form": form, "title": "Open return claim", "eyebrow": "RMA intake"},
    )


@workspace_required
def claim_detail(request, pk):
    claim = get_object_or_404(_claims(request), pk=pk)
    transition_form = TransitionForm(claim=claim, membership=request.membership)
    return render(
        request,
        "returns/claim_detail.html",
        {
            "claim": claim,
            "events": claim.events.select_related("actor"),
            "transition_form": transition_form,
            "can_inspect_now": request.membership.can_inspect
            and claim.status in [ReturnClaim.Status.RECEIVED, ReturnClaim.Status.INSPECTING],
            "public_url": request.build_absolute_uri(
                f"/track/{request.organization.slug}/{claim.tracking_code}/"
            ),
        },
    )


@manager_required
@require_POST
def claim_transition(request, pk):
    claim = get_object_or_404(_claims(request), pk=pk)
    form = TransitionForm(request.POST, claim=claim, membership=request.membership)
    if form.is_valid():
        try:
            transition_claim(
                claim=claim,
                target_status=form.cleaned_data["status"],
                actor=request.user,
                message=form.cleaned_data["update_message"],
                rejection_reason=form.cleaned_data["rejection_reason"],
                resolution=form.cleaned_data["resolution"],
                resolution_summary=form.cleaned_data["resolution_summary"],
                resolution_amount=form.cleaned_data["resolution_amount"] or 0,
                replacement_reference=form.cleaned_data["replacement_reference"],
                visible_to_customer=form.cleaned_data["visible_to_customer"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Claim status updated.")
            return redirect("claim_detail", pk=claim.pk)
    return render(
        request,
        "returns/claim_detail.html",
        {
            "claim": claim,
            "events": claim.events.select_related("actor"),
            "transition_form": form,
            "can_inspect_now": request.membership.can_inspect
            and claim.status in [ReturnClaim.Status.RECEIVED, ReturnClaim.Status.INSPECTING],
            "public_url": request.build_absolute_uri(
                f"/track/{request.organization.slug}/{claim.tracking_code}/"
            ),
        },
        status=400,
    )


@inspector_required
def claim_inspect(request, pk):
    claim = get_object_or_404(_claims(request), pk=pk)
    if claim.status not in [ReturnClaim.Status.RECEIVED, ReturnClaim.Status.INSPECTING]:
        raise PermissionDenied("This item is not ready for inspection.")
    existing = getattr(claim, "inspection", None)
    form = InspectionForm(request.POST or None, instance=existing)
    if request.method == "POST" and form.is_valid():
        try:
            record_inspection(
                claim=claim,
                actor=request.user,
                condition=form.cleaned_data["condition"],
                fault_confirmed=form.cleaned_data["fault_confirmed"],
                findings=form.cleaned_data["findings"],
                recommendation=form.cleaned_data["recommendation"],
                customer_update=form.cleaned_data["customer_update"],
                visible_to_customer=form.cleaned_data["visible_to_customer"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Inspection findings recorded.")
            return redirect("claim_detail", pk=claim.pk)
    return render(
        request,
        "returns/form.html",
        {
            "form": form,
            "title": f"Inspect {claim.tracking_code}",
            "eyebrow": "Technical assessment",
            "claim": claim,
        },
    )


@workspace_required
def catalog(request):
    products = Product.objects.filter(organization=request.organization).annotate(
        item_count=Count("items")
    )
    items = RegisteredItem.objects.filter(organization=request.organization).select_related(
        "product", "customer"
    )[:12]
    return render(request, "returns/catalog.html", {"products": products, "items": items})


@manager_required
def product_create(request):
    form = ProductForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        product = form.save(commit=False)
        product.organization = request.organization
        product.full_clean()
        product.save()
        messages.success(request, f"Product {product.sku} added.")
        return redirect("catalog")
    return render(
        request,
        "returns/form.html",
        {"form": form, "title": "Add product", "eyebrow": "Warranty catalog"},
    )


@manager_required
def item_create(request):
    form = RegisteredItemForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.organization = request.organization
        item.full_clean()
        item.save()
        messages.success(request, f"Serial {item.serial_number} registered.")
        return redirect("catalog")
    return render(
        request,
        "returns/form.html",
        {"form": form, "title": "Register sold item", "eyebrow": "Warranty record"},
    )


@workspace_required
def customer_list(request):
    customers = Customer.objects.filter(organization=request.organization).annotate(
        item_count=Count("items")
    )
    return render(request, "returns/customer_list.html", {"customers": customers})


@manager_required
def customer_create(request):
    form = CustomerForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        customer = form.save(commit=False)
        customer.organization = request.organization
        customer.full_clean()
        customer.save()
        messages.success(request, f"Customer {customer.name} added.")
        return redirect("customer_list")
    return render(
        request,
        "returns/form.html",
        {"form": form, "title": "Add customer", "eyebrow": "Customer registry"},
    )


@workspace_required
def team_list(request):
    memberships = Membership.objects.filter(organization=request.organization).select_related(
        "user"
    )
    return render(request, "returns/team_list.html", {"memberships": memberships})


@manager_required
def team_create(request):
    form = TeamMemberForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"{user.get_full_name() or user.username} can now sign in.")
        return redirect("team_list")
    return render(
        request,
        "returns/form.html",
        {"form": form, "title": "Invite team member", "eyebrow": "Workspace access"},
    )


@require_GET
def public_tracking(request, organization_slug, tracking_code):
    claim = get_object_or_404(
        ReturnClaim.objects.select_related("organization", "item__product", "item__customer"),
        organization__slug=organization_slug,
        tracking_code__iexact=tracking_code,
    )
    return render(
        request,
        "returns/public_tracking.html",
        {"claim": claim, "events": claim.events.filter(visible_to_customer=True)},
    )


def _claim_payload(claim):
    return {
        "id": claim.pk,
        "tracking_code": claim.tracking_code,
        "customer": claim.item.customer.name,
        "product": claim.item.product.name,
        "priority": claim.priority,
        "status": claim.status,
        "requested_remedy": claim.requested_remedy,
        "in_warranty": claim.item.is_in_warranty,
        "response_due": claim.response_due.isoformat(),
        "overdue": claim.is_overdue,
        "resolution": claim.resolution or None,
    }


@workspace_required
@require_GET
def api_summary(request):
    claims = _claims(request)
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "role": request.membership.role,
            "claims": {
                status: claims.filter(status=status).count() for status in ReturnClaim.Status.values
            },
            "overdue": sum(1 for claim in claims if claim.is_overdue),
            "inspection_queue": claims.filter(
                status__in=[ReturnClaim.Status.RECEIVED, ReturnClaim.Status.INSPECTING]
            ).count(),
        }
    )


@workspace_required
@require_GET
def api_claims(request):
    claims = _claims(request)
    status = request.GET.get("status", "")
    if status in ReturnClaim.Status.values:
        claims = claims.filter(status=status)
    return JsonResponse({"results": [_claim_payload(claim) for claim in claims[:100]]})


@workspace_required
@require_GET
def api_catalog(request):
    products = Product.objects.filter(organization=request.organization)
    return JsonResponse(
        {
            "results": [
                {
                    "sku": product.sku,
                    "name": product.name,
                    "category": product.category,
                    "warranty_months": product.warranty_months,
                    "active": product.active,
                }
                for product in products
            ]
        }
    )


@workspace_required
@require_POST
def api_transition(request, pk):
    claim = get_object_or_404(_claims(request), pk=pk)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    try:
        claim = transition_claim(
            claim=claim,
            target_status=payload.get("status", ""),
            actor=request.user,
            message=payload.get("message", ""),
            rejection_reason=payload.get("rejection_reason", ""),
            resolution=payload.get("resolution", ""),
            resolution_summary=payload.get("resolution_summary", ""),
            resolution_amount=payload.get("resolution_amount", 0),
            replacement_reference=payload.get("replacement_reference", ""),
            visible_to_customer=bool(payload.get("visible_to_customer", True)),
        )
    except PermissionDenied as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValidationError as exc:
        error = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        return JsonResponse({"error": error}, status=400)
    return JsonResponse(_claim_payload(claim))
