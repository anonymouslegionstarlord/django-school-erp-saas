from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import (
    ActivityForm,
    ContractForm,
    ContractUpdateForm,
    CounterpartyForm,
    ObligationForm,
    SignupForm,
)
from .models import Activity, Contract, Counterparty, Obligation


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
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@workspace_required
def dashboard(request):
    contracts = Contract.objects.filter(organization=request.organization)
    obligations = Obligation.objects.filter(organization=request.organization)
    today = timezone.localdate()
    attention = contracts.filter(
        status=Contract.Status.ACTIVE, ends_on__lte=today + timedelta(days=60)
    ).select_related("counterparty", "owner")
    context = {
        "active_count": contracts.filter(status=Contract.Status.ACTIVE).count(),
        "active_value": contracts.filter(status=Contract.Status.ACTIVE).aggregate(
            total=Sum("value")
        )["total"]
        or Decimal("0"),
        "attention": attention[:6],
        "overdue": obligations.filter(
            status=Obligation.Status.OPEN, due_on__lt=today
        ).select_related("contract", "assigned_to")[:6],
        "open_obligations": obligations.filter(status=Obligation.Status.OPEN).count(),
        "counterparty_count": Counterparty.objects.filter(
            organization=request.organization
        ).count(),
        "recent": Activity.objects.filter(organization=request.organization).select_related(
            "contract", "author"
        )[:6],
        "status_counts": [
            (label, contracts.filter(status=value).count())
            for value, label in Contract.Status.choices
        ],
    }
    return render(request, "contracts/dashboard.html", context)


@workspace_required
def contract_list(request):
    contracts = Contract.objects.filter(organization=request.organization).select_related(
        "counterparty", "owner"
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if query:
        contracts = contracts.filter(
            Q(title__icontains=query)
            | Q(reference__icontains=query)
            | Q(counterparty__name__icontains=query)
        )
    if status in Contract.Status.values:
        contracts = contracts.filter(status=status)
    return render(
        request,
        "contracts/contract_list.html",
        {
            "contracts": contracts,
            "query": query,
            "status": status,
            "statuses": Contract.Status.choices,
        },
    )


@workspace_required
def contract_create(request):
    if not request.membership.can_manage:
        messages.error(request, "Viewer accounts cannot create contracts.")
        return redirect("contract_list")
    form = ContractForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        contract = form.save(commit=False)
        contract.organization = request.organization
        contract.save()
        Activity.objects.create(
            organization=request.organization,
            contract=contract,
            author=request.user,
            message="Contract created",
        )
        messages.success(request, "Contract created.")
        return redirect("contract_detail", pk=contract.pk)
    return render(request, "contracts/contract_form.html", {"form": form})


@workspace_required
def contract_detail(request, pk):
    contract = get_object_or_404(
        Contract.objects.select_related("counterparty", "owner"),
        pk=pk,
        organization=request.organization,
    )
    return render(
        request,
        "contracts/contract_detail.html",
        {
            "contract": contract,
            "obligations": contract.obligations.select_related("assigned_to"),
            "activities": contract.activities.select_related("author")[:20],
            "update_form": ContractUpdateForm(instance=contract, organization=request.organization),
            "obligation_form": ObligationForm(organization=request.organization),
            "activity_form": ActivityForm(),
        },
    )


@workspace_required
@require_POST
def contract_update(request, pk):
    contract = get_object_or_404(Contract, pk=pk, organization=request.organization)
    if not request.membership.can_manage:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    form = ContractUpdateForm(request.POST, instance=contract, organization=request.organization)
    if form.is_valid():
        form.save()
        Activity.objects.create(
            organization=request.organization,
            contract=contract,
            author=request.user,
            message=f"Status updated to {contract.get_status_display()}",
        )
        messages.success(request, "Contract updated.")
    else:
        messages.error(request, "Please correct the update form.")
    return redirect("contract_detail", pk=pk)


@workspace_required
@require_POST
def obligation_add(request, pk):
    contract = get_object_or_404(Contract, pk=pk, organization=request.organization)
    if not request.membership.can_manage:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    form = ObligationForm(request.POST, organization=request.organization)
    if form.is_valid():
        item = form.save(commit=False)
        item.organization, item.contract = request.organization, contract
        item.save()
        Activity.objects.create(
            organization=request.organization,
            contract=contract,
            author=request.user,
            message=f"Obligation added: {item.title}",
        )
        messages.success(request, "Obligation added.")
    else:
        messages.error(request, "Please correct the obligation form.")
    return redirect("contract_detail", pk=pk)


@workspace_required
@require_POST
def obligation_complete(request, pk):
    item = get_object_or_404(
        Obligation.objects.select_related("contract"), pk=pk, organization=request.organization
    )
    if not request.membership.can_manage:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    item.status, item.completed_at = Obligation.Status.COMPLETED, timezone.now()
    item.save(update_fields=["status", "completed_at"])
    Activity.objects.create(
        organization=request.organization,
        contract=item.contract,
        author=request.user,
        message=f"Obligation completed: {item.title}",
    )
    messages.success(request, "Obligation completed.")
    return redirect("contract_detail", pk=item.contract_id)


@workspace_required
@require_POST
def activity_add(request, pk):
    contract = get_object_or_404(Contract, pk=pk, organization=request.organization)
    form = ActivityForm(request.POST)
    if form.is_valid():
        activity = form.save(commit=False)
        activity.organization, activity.contract, activity.author = (
            request.organization,
            contract,
            request.user,
        )
        activity.save()
    return redirect("contract_detail", pk=pk)


@workspace_required
def counterparties(request):
    form = CounterpartyForm(request.POST or None)
    if request.method == "POST":
        if not request.membership.can_manage:
            return JsonResponse({"detail": "Forbidden"}, status=403)
        if form.is_valid():
            item = form.save(commit=False)
            item.organization = request.organization
            item.save()
            messages.success(request, "Counterparty added.")
            return redirect("counterparties")
    return render(
        request,
        "contracts/counterparties.html",
        {"items": request.organization.counterparties.all(), "form": form},
    )


@workspace_required
def obligation_list(request):
    items = Obligation.objects.filter(organization=request.organization).select_related(
        "contract", "assigned_to"
    )
    return render(request, "contracts/obligation_list.html", {"items": items})


@workspace_required
def api_summary(request):
    contracts = Contract.objects.filter(organization=request.organization)
    obligations = Obligation.objects.filter(organization=request.organization)
    return JsonResponse(
        {
            "active_contracts": contracts.filter(status=Contract.Status.ACTIVE).count(),
            "open_obligations": obligations.filter(status=Obligation.Status.OPEN).count(),
            "counterparties": request.organization.counterparties.count(),
        }
    )


@workspace_required
def api_contracts(request):
    rows = Contract.objects.filter(organization=request.organization).select_related(
        "counterparty", "owner"
    )
    return JsonResponse(
        {
            "results": [
                {
                    "id": item.pk,
                    "reference": item.reference,
                    "title": item.title,
                    "status": item.status,
                    "counterparty": item.counterparty.name,
                    "owner": item.owner.username,
                    "ends_on": item.ends_on.isoformat(),
                    "value": str(item.value),
                }
                for item in rows
            ]
        }
    )


@workspace_required
def api_obligations(request):
    rows = Obligation.objects.filter(organization=request.organization).select_related(
        "contract", "assigned_to"
    )
    return JsonResponse(
        {
            "results": [
                {
                    "id": item.pk,
                    "title": item.title,
                    "contract": item.contract.reference,
                    "status": item.status,
                    "due_on": item.due_on.isoformat(),
                    "assigned_to": item.assigned_to.username,
                }
                for item in rows
            ]
        }
    )
