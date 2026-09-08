import json

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import RequestForm, SignupForm, SubjectForm, TaskForm
from .models import PrivacyRequest, RequestTask
from .services import transition_request, update_task


def workspace(request):
    membership = getattr(request.user, "privacy_membership", None)
    if not membership:
        raise PermissionDenied
    return membership


def landing(request):
    return redirect("dashboard") if request.user.is_authenticated else render(request, "privacy/landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("dashboard")
    return render(request, "privacy/form.html", {"form": form, "title": "Create your workspace", "submit": "Start free"})


@login_required
def dashboard(request):
    membership = workspace(request)
    qs = PrivacyRequest.objects.filter(organization=membership.organization).select_related("subject", "assigned_to")
    return render(
        request,
        "privacy/dashboard.html",
        {
            "requests": qs[:8],
            "total": qs.count(),
            "overdue": sum(item.is_overdue for item in qs),
            "open_count": qs.exclude(status__in=[PrivacyRequest.Status.FULFILLED, PrivacyRequest.Status.REJECTED]).count(),
            "by_status": qs.values("status").annotate(total=Count("id")).order_by("status"),
        },
    )


@login_required
def request_list(request):
    membership = workspace(request)
    qs = PrivacyRequest.objects.filter(organization=membership.organization).select_related("subject", "assigned_to")
    query, status = request.GET.get("q", "").strip(), request.GET.get("status", "")
    if query:
        qs = qs.filter(Q(tracking_code__icontains=query) | Q(subject__name__icontains=query) | Q(subject__email__icontains=query))
    if status in PrivacyRequest.Status.values:
        qs = qs.filter(status=status)
    return render(
        request,
        "privacy/request_list.html",
        {"requests": qs, "query": query, "selected_status": status, "statuses": PrivacyRequest.Status.choices},
    )


@login_required
def request_create(request):
    membership = workspace(request)
    if not membership.can_work:
        raise PermissionDenied
    draft = PrivacyRequest(organization=membership.organization, created_by=request.user)
    form = RequestForm(
        request.POST or None,
        organization=membership.organization,
        instance=draft,
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.organization, item.created_by = membership.organization, request.user
        item.full_clean()
        item.save()
        messages.success(request, "Privacy request created.")
        return redirect("request_detail", pk=item.pk)
    return render(request, "privacy/form.html", {"form": form, "title": "Log privacy request", "submit": "Create request"})


@login_required
def request_detail(request, pk):
    membership = workspace(request)
    item = get_object_or_404(PrivacyRequest.objects.select_related("subject", "assigned_to"), pk=pk, organization=membership.organization)
    return render(
        request,
        "privacy/request_detail.html",
        {
            "item": item,
            "task_form": TaskForm(organization=membership.organization),
            "statuses": PrivacyRequest.Status.choices,
            "task_statuses": RequestTask.Status.choices,
            "can_work": membership.can_work,
            "can_manage": membership.can_manage,
        },
    )


@login_required
def subject_list(request):
    membership = workspace(request)
    form = SubjectForm(request.POST or None)
    if request.method == "POST":
        if not membership.can_work:
            raise PermissionDenied
        if form.is_valid():
            subject = form.save(commit=False)
            subject.organization = membership.organization
            subject.save()
            messages.success(request, "Data subject added.")
            return redirect("subject_list")
    return render(
        request,
        "privacy/subject_list.html",
        {"subjects": membership.organization.subjects.all(), "form": form, "can_work": membership.can_work},
    )


@login_required
@require_POST
def task_create(request, pk):
    membership = workspace(request)
    if not membership.can_work:
        raise PermissionDenied
    item = get_object_or_404(PrivacyRequest, pk=pk, organization=membership.organization)
    form = TaskForm(
        request.POST,
        organization=membership.organization,
        instance=RequestTask(request=item),
    )
    if form.is_valid():
        task = form.save(commit=False)
        task.request = item
        task.full_clean()
        task.save()
        messages.success(request, "Task added.")
    else:
        messages.error(request, "Please correct the task details.")
    return redirect("request_detail", pk=pk)


@login_required
@require_POST
def transition(request, pk):
    try:
        transition_request(
            pk, request.user, request.POST.get("status", ""), request.POST.get("note", ""), request.POST.get("delivery_reference", "")
        )
        messages.success(request, "Workflow updated.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else "You cannot perform that action.")
    return redirect("request_detail", pk=pk)


@login_required
@require_POST
def task_update(request, pk):
    membership = workspace(request)
    task = get_object_or_404(RequestTask.objects.select_related("request"), pk=pk, request__organization=membership.organization)
    try:
        update_task(task, request.user, request.POST.get("status", ""), request.POST.get("notes", ""))
        messages.success(request, "Task updated.")
    except (ValidationError, PermissionDenied):
        raise PermissionDenied from None
    return redirect("request_detail", pk=task.request_id)


def public_tracking(request, code):
    item = get_object_or_404(PrivacyRequest.objects.select_related("subject"), tracking_code=code)
    return render(request, "privacy/public_tracking.html", {"item": item, "events": item.events.filter(visible_to_subject=True)})


@login_required
def api_requests(request):
    membership = workspace(request)
    qs = PrivacyRequest.objects.filter(organization=membership.organization).select_related("subject")
    return JsonResponse(
        {
            "results": [
                {
                    "id": x.id,
                    "tracking_code": x.tracking_code,
                    "subject": x.subject.name,
                    "type": x.kind,
                    "status": x.status,
                    "due_at": x.due_at.isoformat(),
                    "overdue": x.is_overdue,
                }
                for x in qs
            ]
        }
    )


@login_required
@require_POST
def api_transition(request, pk):
    try:
        payload = json.loads(request.body or "{}")
        item = transition_request(
            pk, request.user, payload.get("status", ""), payload.get("note", ""), payload.get("delivery_reference", "")
        )
        return JsonResponse({"id": item.id, "status": item.status})
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    except PrivacyRequest.DoesNotExist:
        return JsonResponse({"error": "Not found."}, status=404)
    except PermissionDenied:
        return JsonResponse({"error": "Forbidden."}, status=403)
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
