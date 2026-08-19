from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import ClientForm, InvoiceForm, LineItemForm, PaymentForm, SignupForm
from .models import Client, Invoice


def landing(request):
    return redirect("dashboard") if request.user.is_authenticated else render(request, "billing/landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your BillForge workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@workspace_required
def dashboard(request):
    invoices = Invoice.objects.filter(organization=request.organization).select_related("client").prefetch_related("items", "payments")
    open_invoices = [i for i in invoices if i.status not in {Invoice.Status.PAID, Invoice.Status.VOID}]
    context = {
        "invoice_count": invoices.count(),
        "outstanding": sum((i.balance for i in open_invoices), Decimal("0")),
        "overdue_count": sum(i.is_overdue for i in open_invoices),
        "collected": sum((i.paid_amount for i in invoices), Decimal("0")),
        "recent_invoices": invoices[:7],
        "client_count": Client.objects.filter(organization=request.organization).count(),
    }
    return render(request, "billing/dashboard.html", context)


@workspace_required
def clients(request):
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organization = request.organization
        obj.save()
        messages.success(request, "Client added.")
        return redirect("clients")
    return render(request, "billing/clients.html", {"form": form, "clients": Client.objects.filter(organization=request.organization)})


@workspace_required
def invoices(request):
    rows = Invoice.objects.filter(organization=request.organization).select_related("client").prefetch_related("items", "payments")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if query:
        rows = rows.filter(Q(number__icontains=query) | Q(client__name__icontains=query))
    if status in Invoice.Status.values:
        rows = rows.filter(status=status)
    return render(
        request, "billing/invoices.html", {"invoices": rows, "query": query, "selected_status": status, "statuses": Invoice.Status.choices}
    )


@workspace_required
def create_invoice(request):
    form = InvoiceForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        invoice = form.save(commit=False)
        invoice.organization = request.organization
        invoice.save()
        messages.success(request, "Invoice created. Add at least one line item.")
        return redirect("invoice_detail", pk=invoice.pk)
    return render(request, "billing/invoice_form.html", {"form": form})


@workspace_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related("client").prefetch_related("items", "payments"), pk=pk, organization=request.organization
    )
    return render(request, "billing/invoice_detail.html", {"invoice": invoice, "item_form": LineItemForm(), "payment_form": PaymentForm()})


@require_POST
@workspace_required
def add_item(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, organization=request.organization)
    form = LineItemForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        item.invoice = invoice
        item.save()
        messages.success(request, "Line item added.")
    else:
        messages.error(request, "Check the line item values.")
    return redirect("invoice_detail", pk=pk)


@require_POST
@workspace_required
def add_payment(request, pk):
    invoice = get_object_or_404(Invoice.objects.prefetch_related("items", "payments"), pk=pk, organization=request.organization)
    form = PaymentForm(request.POST)
    balance_before_payment = invoice.balance
    if form.is_valid() and form.cleaned_data["amount"] <= balance_before_payment:
        payment = form.save(commit=False)
        payment.invoice = invoice
        payment.organization = request.organization
        payment.save()
        if form.cleaned_data["amount"] == balance_before_payment:
            invoice.status = Invoice.Status.PAID
            invoice.save(update_fields=["status"])
        messages.success(request, "Payment recorded.")
    else:
        messages.error(request, "Payment must be valid and cannot exceed the balance.")
    return redirect("invoice_detail", pk=pk)


@require_POST
@workspace_required
def update_status(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, organization=request.organization)
    status = request.POST.get("status")
    if status in Invoice.Status.values:
        invoice.status = status
        invoice.save(update_fields=["status"])
        messages.success(request, "Invoice status updated.")
    return redirect("invoice_detail", pk=pk)


def serialize_invoice(i):
    return {
        "id": i.id,
        "number": i.number,
        "client": i.client.name,
        "status": i.status,
        "total": str(i.total),
        "balance": str(i.balance),
        "due_date": i.due_date,
        "overdue": i.is_overdue,
    }


@workspace_required
def api_summary(request):
    invoices = Invoice.objects.filter(organization=request.organization).prefetch_related("items", "payments")
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "clients": Client.objects.filter(organization=request.organization).count(),
            "invoices": invoices.count(),
            "outstanding": str(sum((i.balance for i in invoices if i.status not in {"paid", "void"}), Decimal("0"))),
        }
    )


@workspace_required
def api_invoices(request):
    rows = Invoice.objects.filter(organization=request.organization).select_related("client").prefetch_related("items", "payments")
    return JsonResponse({"results": [serialize_invoice(i) for i in rows]})


@workspace_required
def api_clients(request):
    return JsonResponse(
        {"results": list(Client.objects.filter(organization=request.organization).values("id", "name", "email", "company"))}
    )
