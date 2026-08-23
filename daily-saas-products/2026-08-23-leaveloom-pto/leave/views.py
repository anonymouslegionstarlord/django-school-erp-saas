from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import LeaveRequestForm, SignupForm
from .models import LeaveRequest, Membership


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "leave/landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your LeaveLoom workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def leave_used(user, organization):
    return sum(
        request.business_days
        for request in LeaveRequest.objects.filter(
            organization=organization,
            requester=user,
            status=LeaveRequest.Status.APPROVED,
            starts_on__year=timezone.localdate().year,
        )
    )


@workspace_required
def dashboard(request):
    tenant_requests = LeaveRequest.objects.filter(organization=request.organization).select_related(
        "requester", "leave_type", "reviewed_by"
    )
    used = leave_used(request.user, request.organization)
    upcoming = tenant_requests.filter(
        status=LeaveRequest.Status.APPROVED, ends_on__gte=timezone.localdate()
    ).order_by("starts_on")[:6]
    context = {
        "allowance": request.membership.annual_allowance,
        "used": used,
        "remaining": max(request.membership.annual_allowance - used, 0),
        "my_pending": tenant_requests.filter(
            requester=request.user, status=LeaveRequest.Status.PENDING
        ).count(),
        "upcoming": upcoming,
        "my_recent": tenant_requests.filter(requester=request.user)[:5],
        "approval_queue": tenant_requests.filter(status=LeaveRequest.Status.PENDING).exclude(
            requester=request.user
        )[:6]
        if request.membership.can_review
        else [],
    }
    return render(request, "leave/dashboard.html", context)


@workspace_required
def requests_list(request):
    scope = request.GET.get("scope", "mine")
    rows = LeaveRequest.objects.filter(organization=request.organization).select_related(
        "requester", "leave_type", "reviewed_by"
    )
    if scope != "team" or not request.membership.can_review:
        scope = "mine"
        rows = rows.filter(requester=request.user)
    return render(request, "leave/requests.html", {"requests": rows, "scope": scope})


@workspace_required
def create_request(request):
    form = LeaveRequestForm(
        request.POST or None, organization=request.organization, requester=request.user
    )
    if request.method == "POST" and form.is_valid():
        leave_request = form.save(commit=False)
        leave_request.organization = request.organization
        leave_request.requester = request.user
        leave_request.save()
        messages.success(request, "Leave request submitted for review.")
        return redirect("requests")
    return render(request, "leave/request_form.html", {"form": form})


@require_POST
@workspace_required
def review_request(request, pk):
    leave_request = get_object_or_404(
        LeaveRequest, pk=pk, organization=request.organization, status=LeaveRequest.Status.PENDING
    )
    if not request.membership.can_review:
        messages.error(request, "Only owners and managers can review leave requests.")
    elif leave_request.requester_id == request.user.id:
        messages.error(request, "You cannot approve your own leave request.")
    else:
        decision = request.POST.get("decision")
        if decision in [LeaveRequest.Status.APPROVED, LeaveRequest.Status.REJECTED]:
            leave_request.status = decision
            leave_request.reviewed_by = request.user
            leave_request.reviewed_at = timezone.now()
            leave_request.review_note = request.POST.get("review_note", "")[:500]
            leave_request.save(
                update_fields=["status", "reviewed_by", "reviewed_at", "review_note"]
            )
            messages.success(request, f"Request {decision}.")
    return redirect("requests")


@require_POST
@workspace_required
def cancel_request(request, pk):
    leave_request = get_object_or_404(
        LeaveRequest,
        pk=pk,
        organization=request.organization,
        requester=request.user,
        status=LeaveRequest.Status.PENDING,
    )
    leave_request.status = LeaveRequest.Status.CANCELLED
    leave_request.save(update_fields=["status"])
    messages.success(request, "Leave request cancelled.")
    return redirect("requests")


@workspace_required
def team_calendar(request):
    month = request.GET.get("month") or timezone.localdate().strftime("%Y-%m")
    try:
        year, month_number = map(int, month.split("-"))
    except (TypeError, ValueError):
        year, month_number = timezone.localdate().year, timezone.localdate().month
        month = f"{year:04d}-{month_number:02d}"
    rows = LeaveRequest.objects.filter(
        organization=request.organization,
        status=LeaveRequest.Status.APPROVED,
        starts_on__year=year,
    ).filter(Q(starts_on__month=month_number) | Q(ends_on__month=month_number))
    return render(
        request,
        "leave/calendar.html",
        {"requests": rows.select_related("requester", "leave_type"), "month": month},
    )


@workspace_required
def team(request):
    members = Membership.objects.filter(organization=request.organization).select_related("user")
    rows = [
        {
            "membership": member,
            "used": leave_used(member.user, request.organization),
            "remaining": max(
                member.annual_allowance - leave_used(member.user, request.organization), 0
            ),
        }
        for member in members
    ]
    return render(request, "leave/team.html", {"members": rows})


@workspace_required
def api_summary(request):
    rows = LeaveRequest.objects.filter(organization=request.organization)
    used = leave_used(request.user, request.organization)
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "allowance": request.membership.annual_allowance,
            "used": used,
            "remaining": max(request.membership.annual_allowance - used, 0),
            "pending_team_requests": rows.filter(status=LeaveRequest.Status.PENDING).count(),
        }
    )


def request_payload(item):
    return {
        "id": item.id,
        "employee": item.requester.get_full_name() or item.requester.username,
        "leave_type": item.leave_type.name,
        "starts_on": item.starts_on,
        "ends_on": item.ends_on,
        "business_days": item.business_days,
        "status": item.status,
    }


@workspace_required
def api_requests(request):
    rows = LeaveRequest.objects.filter(organization=request.organization).select_related(
        "requester", "leave_type"
    )
    if not request.membership.can_review:
        rows = rows.filter(requester=request.user)
    return JsonResponse({"results": [request_payload(item) for item in rows]})


@workspace_required
def api_calendar(request):
    rows = LeaveRequest.objects.filter(
        organization=request.organization, status=LeaveRequest.Status.APPROVED
    ).select_related("requester", "leave_type")
    return JsonResponse({"results": [request_payload(item) for item in rows]})
