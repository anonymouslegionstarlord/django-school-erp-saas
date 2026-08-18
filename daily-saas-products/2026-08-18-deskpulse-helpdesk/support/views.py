from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import CustomerForm, ReplyForm, SignupForm, TicketForm
from .models import Customer, Ticket


def landing(request):
    return redirect("dashboard") if request.user.is_authenticated else render(request, "support/landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your DeskPulse workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@workspace_required
def dashboard(request):
    tickets = Ticket.objects.filter(organization=request.organization).select_related("customer", "assigned_to")
    active = tickets.exclude(status=Ticket.Status.RESOLVED)
    today = timezone.localdate()
    context = {
        "open_count": tickets.filter(status=Ticket.Status.OPEN).count(),
        "active_count": active.count(),
        "urgent_count": active.filter(priority=Ticket.Priority.URGENT).count(),
        "overdue_count": active.filter(due_at__lt=timezone.now()).count(),
        "resolved_today": tickets.filter(status=Ticket.Status.RESOLVED, updated_at__date=today).count(),
        "recent_tickets": tickets[:7],
        "status_counts": [(label, tickets.filter(status=value).count()) for value, label in Ticket.Status.choices],
    }
    return render(request, "support/dashboard.html", context)


@workspace_required
def customers(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save(commit=False)
        customer.organization = request.organization
        customer.save()
        messages.success(request, "Customer added.")
        return redirect("customers")
    rows = Customer.objects.filter(organization=request.organization).annotate(ticket_count=Count("tickets"))
    return render(request, "support/customers.html", {"form": form, "customers": rows})


@workspace_required
def tickets(request):
    rows = Ticket.objects.filter(organization=request.organization).select_related("customer", "assigned_to")
    status = request.GET.get("status", "")
    priority = request.GET.get("priority", "")
    query = request.GET.get("q", "").strip()
    if status in Ticket.Status.values:
        rows = rows.filter(status=status)
    if priority in Ticket.Priority.values:
        rows = rows.filter(priority=priority)
    if query:
        rows = rows.filter(Q(subject__icontains=query) | Q(customer__name__icontains=query) | Q(customer__email__icontains=query))
    return render(
        request,
        "support/tickets.html",
        {
            "tickets": rows,
            "statuses": Ticket.Status.choices,
            "priorities": Ticket.Priority.choices,
            "selected_status": status,
            "selected_priority": priority,
            "query": query,
        },
    )


@workspace_required
def create_ticket(request):
    form = TicketForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.organization = request.organization
        ticket.save()
        messages.success(request, f"Ticket #{ticket.pk} created.")
        return redirect("ticket_detail", pk=ticket.pk)
    return render(request, "support/ticket_form.html", {"form": form})


@workspace_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket.objects.select_related("customer", "assigned_to"), pk=pk, organization=request.organization)
    form = ReplyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        reply = form.save(commit=False)
        reply.organization = request.organization
        reply.ticket = ticket
        reply.author = request.user
        reply.save()
        ticket.save(update_fields=["updated_at"])
        messages.success(request, "Response added.")
        return redirect("ticket_detail", pk=ticket.pk)
    return render(request, "support/ticket_detail.html", {"ticket": ticket, "form": form})


@require_POST
@workspace_required
def update_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, organization=request.organization)
    status = request.POST.get("status")
    priority = request.POST.get("priority")
    if status in Ticket.Status.values:
        ticket.status = status
    if priority in Ticket.Priority.values:
        ticket.priority = priority
    ticket.save()
    messages.success(request, "Ticket updated.")
    return redirect("ticket_detail", pk=ticket.pk)


def _ticket_payload(ticket):
    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "customer": ticket.customer.name,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to": ticket.assigned_to.username if ticket.assigned_to else None,
        "due_at": ticket.due_at,
    }


@workspace_required
def api_summary(request):
    tickets = Ticket.objects.filter(organization=request.organization)
    active = tickets.exclude(status=Ticket.Status.RESOLVED)
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "customers": Customer.objects.filter(organization=request.organization).count(),
            "active_tickets": active.count(),
            "overdue": active.filter(due_at__lt=timezone.now()).count(),
        }
    )


@workspace_required
def api_tickets(request):
    rows = Ticket.objects.filter(organization=request.organization).select_related("customer", "assigned_to")
    return JsonResponse({"results": [_ticket_payload(ticket) for ticket in rows]})


@workspace_required
def api_customers(request):
    rows = Customer.objects.filter(organization=request.organization).values("id", "name", "email", "company")
    return JsonResponse({"results": list(rows)})
