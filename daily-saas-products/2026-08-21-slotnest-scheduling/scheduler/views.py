from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .decorators import workspace_required
from .forms import AppointmentForm, CustomerForm, ServiceForm, SignupForm
from .models import Appointment, Customer, Service


def landing(request):
    return (
        redirect("dashboard")
        if request.user.is_authenticated
        else render(request, "scheduler/landing.html")
    )


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your SlotNest workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@workspace_required
def dashboard(request):
    appointments = Appointment.objects.filter(organization=request.organization).select_related(
        "customer", "service", "staff"
    )
    today = timezone.localdate()
    today_rows = appointments.filter(starts_at__date=today)
    context = {
        "today_count": today_rows.exclude(status=Appointment.Status.CANCELLED).count(),
        "upcoming_count": appointments.filter(
            starts_at__gte=timezone.now(), status=Appointment.Status.CONFIRMED
        ).count(),
        "completed_count": appointments.filter(status=Appointment.Status.COMPLETED).count(),
        "revenue": sum((a.revenue for a in appointments), Decimal("0")),
        "today_rows": today_rows,
        "next_rows": appointments.filter(starts_at__gte=timezone.now()).exclude(
            status=Appointment.Status.CANCELLED
        )[:6],
    }
    return render(request, "scheduler/dashboard.html", context)


@workspace_required
def schedule(request):
    date_value = request.GET.get("date") or timezone.localdate().isoformat()
    rows = Appointment.objects.filter(
        organization=request.organization, starts_at__date=date_value
    ).select_related("customer", "service", "staff")
    return render(
        request, "scheduler/schedule.html", {"appointments": rows, "selected_date": date_value}
    )


@workspace_required
def services(request):
    form = ServiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        o = form.save(commit=False)
        o.organization = request.organization
        o.save()
        messages.success(request, "Service added.")
        return redirect("services")
    return render(
        request,
        "scheduler/services.html",
        {"form": form, "services": Service.objects.filter(organization=request.organization)},
    )


@workspace_required
def customers(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        o = form.save(commit=False)
        o.organization = request.organization
        o.save()
        messages.success(request, "Customer added.")
        return redirect("customers")
    rows = Customer.objects.filter(organization=request.organization).annotate(
        booking_count=Count("appointments")
    )
    return render(request, "scheduler/customers.html", {"form": form, "customers": rows})


@workspace_required
def create_appointment(request):
    form = AppointmentForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        a = form.save(commit=False)
        a.organization = request.organization
        a.save()
        messages.success(request, "Appointment booked.")
        return redirect("appointment_detail", pk=a.pk)
    return render(request, "scheduler/appointment_form.html", {"form": form})


@workspace_required
def appointment_detail(request, pk):
    appointment = get_object_or_404(
        Appointment.objects.select_related("customer", "service", "staff"),
        pk=pk,
        organization=request.organization,
    )
    return render(request, "scheduler/appointment_detail.html", {"appointment": appointment})


@require_POST
@workspace_required
def update_status(request, pk):
    a = get_object_or_404(Appointment, pk=pk, organization=request.organization)
    status = request.POST.get("status")
    if status in Appointment.Status.values:
        a.status = status
        a.save(update_fields=["status"])
        messages.success(request, "Appointment updated.")
    return redirect("appointment_detail", pk=pk)


def payload(a):
    return {
        "id": a.id,
        "customer": a.customer.name,
        "service": a.service.name,
        "staff": a.staff.username,
        "starts_at": a.starts_at,
        "ends_at": a.ends_at,
        "status": a.status,
        "price": str(a.service.price),
    }


@workspace_required
def api_summary(request):
    rows = Appointment.objects.filter(organization=request.organization)
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "services": Service.objects.filter(
                organization=request.organization, active=True
            ).count(),
            "customers": Customer.objects.filter(organization=request.organization).count(),
            "upcoming": rows.filter(starts_at__gte=timezone.now(), status="confirmed").count(),
        }
    )


@workspace_required
def api_appointments(request):
    rows = Appointment.objects.filter(organization=request.organization).select_related(
        "customer", "service", "staff"
    )
    return JsonResponse({"results": [payload(a) for a in rows]})


@workspace_required
def api_services(request):
    return JsonResponse(
        {
            "results": list(
                Service.objects.filter(organization=request.organization).values(
                    "id", "name", "duration_minutes", "price", "active"
                )
            )
        }
    )
