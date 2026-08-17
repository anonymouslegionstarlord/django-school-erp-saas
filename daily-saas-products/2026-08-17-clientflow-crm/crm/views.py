from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import ContactForm, DealForm, SignupForm
from .models import Activity, Contact, Deal


def landing(request):
    return redirect("dashboard") if request.user.is_authenticated else render(request, "crm/landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your ClientFlow workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@workspace_required
def dashboard(request):
    org = request.organization
    deals = Deal.objects.filter(organization=org).select_related("contact")
    open_deals = deals.exclude(stage__in=[Deal.Stage.WON, Deal.Stage.LOST])
    context = {
        "contact_count": Contact.objects.filter(organization=org).count(),
        "open_count": open_deals.count(),
        "pipeline_value": open_deals.aggregate(total=Sum("value"))["total"] or Decimal("0"),
        "won_value": deals.filter(stage=Deal.Stage.WON).aggregate(total=Sum("value"))["total"] or Decimal("0"),
        "recent_deals": deals[:6],
        "activities": Activity.objects.filter(organization=org).select_related("deal", "created_by")[:6],
        "stage_counts": [(label, deals.filter(stage=value).count()) for value, label in Deal.Stage.choices],
    }
    return render(request, "crm/dashboard.html", context)


@workspace_required
def contacts(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        contact = form.save(commit=False)
        contact.organization = request.organization
        contact.save()
        messages.success(request, "Contact added.")
        return redirect("contacts")
    return render(request, "crm/contacts.html", {"form": form, "contacts": Contact.objects.filter(organization=request.organization)})


@workspace_required
def deals(request):
    form = DealForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        deal = form.save(commit=False)
        deal.organization = request.organization
        deal.save()
        messages.success(request, "Deal added to your pipeline.")
        return redirect("deals")
    rows = Deal.objects.filter(organization=request.organization).select_related("contact")
    columns = [(value, label, rows.filter(stage=value)) for value, label in Deal.Stage.choices]
    return render(request, "crm/deals.html", {"form": form, "columns": columns})


@require_POST
@workspace_required
def update_stage(request, pk):
    deal = get_object_or_404(Deal, pk=pk, organization=request.organization)
    stage = request.POST.get("stage")
    if stage in Deal.Stage.values:
        deal.stage = stage
        deal.save(update_fields=["stage"])
        messages.success(request, "Deal stage updated.")
    return redirect("deals")


@require_POST
@workspace_required
def add_activity(request, pk):
    deal = get_object_or_404(Deal, pk=pk, organization=request.organization)
    kind = request.POST.get("kind")
    notes = request.POST.get("notes", "").strip()
    if kind in Activity.Kind.values and notes:
        Activity.objects.create(organization=request.organization, deal=deal, kind=kind, notes=notes, created_by=request.user)
        messages.success(request, "Activity recorded.")
    return redirect("deals")


def _serialize_deal(deal):
    return {
        "id": deal.id,
        "title": deal.title,
        "contact": deal.contact.name,
        "value": str(deal.value),
        "stage": deal.stage,
        "expected_close": deal.expected_close,
    }


@workspace_required
def api_summary(request):
    deals = Deal.objects.filter(organization=request.organization)
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "contacts": Contact.objects.filter(organization=request.organization).count(),
            "deals": deals.count(),
            "pipeline_value": str(deals.exclude(stage__in=["won", "lost"]).aggregate(total=Sum("value"))["total"] or 0),
        }
    )


@workspace_required
def api_contacts(request):
    data = Contact.objects.filter(organization=request.organization).values("id", "name", "company", "email", "phone")
    return JsonResponse({"results": list(data)})


@workspace_required
def api_deals(request):
    data = Deal.objects.filter(organization=request.organization).select_related("contact")
    return JsonResponse({"results": [_serialize_deal(deal) for deal in data]})
