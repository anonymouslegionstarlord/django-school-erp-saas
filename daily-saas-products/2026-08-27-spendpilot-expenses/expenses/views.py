from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import (
    CommentForm,
    CostCenterForm,
    DecisionForm,
    ExpenseCategoryForm,
    ExpenseItemForm,
    ExpenseReportForm,
    SignupForm,
)
from .models import Activity, ExpenseItem, ExpenseReport


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
        messages.success(request, "Your spend workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def visible_reports(request):
    reports = ExpenseReport.objects.filter(organization=request.organization).select_related(
        "submitter", "cost_center", "reviewed_by"
    )
    if not request.membership.can_view_all:
        reports = reports.filter(submitter=request.user)
    return reports


def get_visible_report(request, pk):
    return get_object_or_404(visible_reports(request), pk=pk)


def record_activity(report, actor, action, message):
    return Activity.objects.create(
        organization=report.organization,
        report=report,
        actor=actor,
        action=action,
        message=message,
    )


@workspace_required
def dashboard(request):
    reports = visible_reports(request)
    organization = request.organization
    month_start = timezone.localdate().replace(day=1)
    approved_items = ExpenseItem.objects.filter(
        organization=organization,
        expense_date__gte=month_start,
        report__status__in=[ExpenseReport.Status.APPROVED, ExpenseReport.Status.REIMBURSED],
    )
    if not request.membership.can_view_all:
        approved_items = approved_items.filter(report__submitter=request.user)
    category_spend = list(
        approved_items.values("category__name").annotate(total=Sum("amount")).order_by("-total")[:5]
    )
    flagged_items = ExpenseItem.objects.filter(
        organization=organization,
    ).exclude(policy_note="")
    if not request.membership.can_view_all:
        flagged_items = flagged_items.filter(report__submitter=request.user)
    context = {
        "pending_count": reports.filter(status=ExpenseReport.Status.SUBMITTED).count(),
        "approved_spend": approved_items.aggregate(total=Sum("amount"))["total"] or Decimal("0.00"),
        "awaiting_reimbursement": reports.filter(status=ExpenseReport.Status.APPROVED).count(),
        "policy_issue_count": flagged_items.filter(
            report__status__in=[ExpenseReport.Status.DRAFT, ExpenseReport.Status.SUBMITTED]
        ).count(),
        "recent_reports": reports[:7],
        "review_queue": ExpenseReport.objects.filter(
            organization=organization, status=ExpenseReport.Status.SUBMITTED
        )
        .exclude(submitter=request.user)
        .select_related("submitter", "cost_center")[:6]
        if request.membership.can_review
        else [],
        "reimbursement_queue": ExpenseReport.objects.filter(
            organization=organization, status=ExpenseReport.Status.APPROVED
        ).select_related("submitter", "cost_center")[:6]
        if request.membership.can_reimburse
        else [],
        "category_spend": category_spend,
    }
    return render(request, "expenses/dashboard.html", context)


@workspace_required
def report_list(request):
    reports = visible_reports(request)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if query:
        filters = (
            Q(title__icontains=query)
            | Q(purpose__icontains=query)
            | Q(submitter__username__icontains=query)
            | Q(submitter__first_name__icontains=query)
            | Q(cost_center__code__icontains=query)
        )
        if query.upper().startswith("SP-") and query[3:].isdigit():
            filters |= Q(pk=int(query[3:]))
        reports = reports.filter(filters).distinct()
    if status in ExpenseReport.Status.values:
        reports = reports.filter(status=status)
    return render(
        request,
        "expenses/report_list.html",
        {
            "reports": reports,
            "query": query,
            "status": status,
            "statuses": ExpenseReport.Status.choices,
        },
    )


@workspace_required
def report_create(request):
    form = ExpenseReportForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.organization = request.organization
        report.submitter = request.user
        report.full_clean()
        report.save()
        record_activity(
            report,
            request.user,
            Activity.Action.CREATED,
            "Expense report created",
        )
        messages.success(request, "Draft report created. Add expenses before submitting it.")
        return redirect("report_detail", pk=report.pk)
    return render(request, "expenses/report_form.html", {"form": form, "report": None})


@workspace_required
def report_edit(request, pk):
    report = get_visible_report(request, pk)
    if report.submitter != request.user or not report.is_editable:
        return HttpResponseForbidden("Only the submitter can edit a draft or rejected report.")
    form = ExpenseReportForm(
        request.POST or None, instance=report, organization=request.organization
    )
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        if report.status == ExpenseReport.Status.REJECTED:
            report.status = ExpenseReport.Status.DRAFT
            report.reviewed_by = None
            report.decided_at = None
            report.decision_note = ""
        report.full_clean()
        report.save()
        record_activity(
            report,
            request.user,
            Activity.Action.COMMENTED,
            "Report details updated",
        )
        messages.success(request, "Report updated.")
        return redirect("report_detail", pk=report.pk)
    return render(request, "expenses/report_form.html", {"form": form, "report": report})


@workspace_required
def report_detail(request, pk):
    report = get_visible_report(request, pk)
    return render(
        request,
        "expenses/report_detail.html",
        {
            "report": report,
            "items": report.items.select_related("category"),
            "activities": report.activities.select_related("actor")[:30],
            "item_form": ExpenseItemForm(organization=request.organization),
            "decision_form": DecisionForm(),
            "comment_form": CommentForm(),
        },
    )


@workspace_required
@require_POST
def item_add(request, pk):
    report = get_visible_report(request, pk)
    if report.submitter != request.user or not report.is_editable:
        return HttpResponseForbidden("Only the submitter can add expenses to an editable report.")
    form = ExpenseItemForm(request.POST, organization=request.organization)
    if form.is_valid():
        with transaction.atomic():
            if report.status == ExpenseReport.Status.REJECTED:
                report.status = ExpenseReport.Status.DRAFT
                report.reviewed_by = None
                report.decided_at = None
                report.decision_note = ""
                report.save(update_fields=["status", "reviewed_by", "decided_at", "decision_note"])
            item = form.save(commit=False)
            item.organization = request.organization
            item.report = report
            item.full_clean()
            item.save()
            message = f"Added {item.category.name} expense at {item.merchant}"
            if item.policy_note:
                message += f" — policy flag: {item.policy_note}"
            record_activity(
                report,
                request.user,
                Activity.Action.ITEM_ADDED,
                message,
            )
        messages.success(request, "Expense added and policy rules evaluated.")
    else:
        messages.error(request, "Please correct the expense item form.")
    return redirect("report_detail", pk=pk)


@workspace_required
@require_POST
def item_delete(request, pk, item_pk):
    report = get_visible_report(request, pk)
    item = get_object_or_404(
        ExpenseItem, pk=item_pk, report=report, organization=request.organization
    )
    if report.submitter != request.user or not report.is_editable:
        return HttpResponseForbidden("Only the submitter can remove editable expenses.")
    merchant = item.merchant
    item.delete()
    record_activity(
        report,
        request.user,
        Activity.Action.COMMENTED,
        f"Removed expense from {merchant}",
    )
    messages.success(request, "Expense removed.")
    return redirect("report_detail", pk=pk)


@workspace_required
@require_POST
def report_submit(request, pk):
    report = get_visible_report(request, pk)
    if report.submitter != request.user or not report.is_editable:
        return HttpResponseForbidden("This report cannot be submitted by this account.")
    if not report.items.exists():
        messages.error(request, "Add at least one expense before submitting the report.")
        return redirect("report_detail", pk=pk)
    report.status = ExpenseReport.Status.SUBMITTED
    report.submitted_at = timezone.now()
    report.reviewed_by = None
    report.decided_at = None
    report.decision_note = ""
    report.save(
        update_fields=[
            "status",
            "submitted_at",
            "reviewed_by",
            "decided_at",
            "decision_note",
            "updated_at",
        ]
    )
    record_activity(
        report,
        request.user,
        Activity.Action.SUBMITTED,
        f"Submitted for approval with {report.policy_issue_count} policy flag(s)",
    )
    messages.success(request, "Report submitted for approval.")
    return redirect("report_detail", pk=pk)


@workspace_required
@require_POST
def report_decide(request, pk):
    report = get_object_or_404(ExpenseReport, pk=pk, organization=request.organization)
    if not request.membership.can_review:
        return HttpResponseForbidden("Only owners and managers can review reports.")
    if report.submitter == request.user:
        return HttpResponseForbidden("Self-approval is not allowed.")
    if report.status != ExpenseReport.Status.SUBMITTED:
        messages.error(request, "Only submitted reports can be reviewed.")
        return redirect("report_detail", pk=pk)
    action = request.POST.get("action")
    form = DecisionForm(request.POST)
    if action not in ["approve", "reject"] or not form.is_valid():
        messages.error(request, "Choose a valid approval decision.")
        return redirect("report_detail", pk=pk)
    note = form.cleaned_data["note"].strip()
    if action == "reject" and not note:
        messages.error(request, "A rejection reason is required.")
        return redirect("report_detail", pk=pk)
    if action == "approve" and report.policy_issue_count and not note:
        messages.error(request, "Explain the policy exception before approving this report.")
        return redirect("report_detail", pk=pk)
    report.status = (
        ExpenseReport.Status.APPROVED if action == "approve" else ExpenseReport.Status.REJECTED
    )
    report.reviewed_by = request.user
    report.decided_at = timezone.now()
    report.decision_note = note
    report.save(
        update_fields=["status", "reviewed_by", "decided_at", "decision_note", "updated_at"]
    )
    activity_action = Activity.Action.APPROVED if action == "approve" else Activity.Action.REJECTED
    record_activity(
        report,
        request.user,
        activity_action,
        f"{report.get_status_display()} by {request.user.username}"
        + (f" — {note}" if note else ""),
    )
    messages.success(request, f"Report {report.get_status_display().lower()}.")
    return redirect("report_detail", pk=pk)


@workspace_required
@require_POST
def report_reimburse(request, pk):
    report = get_object_or_404(ExpenseReport, pk=pk, organization=request.organization)
    if not request.membership.can_reimburse:
        return HttpResponseForbidden("Only owners and finance users can record reimbursement.")
    if report.status != ExpenseReport.Status.APPROVED:
        messages.error(request, "Only approved reports can be reimbursed.")
        return redirect("report_detail", pk=pk)
    report.status = ExpenseReport.Status.REIMBURSED
    report.reimbursed_at = timezone.now()
    report.save(update_fields=["status", "reimbursed_at", "updated_at"])
    record_activity(
        report,
        request.user,
        Activity.Action.REIMBURSED,
        f"Reimbursement recorded by {request.user.username}",
    )
    messages.success(request, "Report marked as reimbursed.")
    return redirect("report_detail", pk=pk)


@workspace_required
@require_POST
def comment_add(request, pk):
    report = get_visible_report(request, pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        record_activity(
            report,
            request.user,
            Activity.Action.COMMENTED,
            form.cleaned_data["message"],
        )
        messages.success(request, "Comment added to the audit trail.")
    return redirect("report_detail", pk=pk)


@workspace_required
def policy_settings(request):
    if not request.membership.can_configure:
        return HttpResponseForbidden("Only owners and finance users can configure spend policy.")
    cost_center_form = CostCenterForm(organization=request.organization)
    category_form = ExpenseCategoryForm(organization=request.organization)
    if request.method == "POST":
        kind = request.POST.get("kind")
        if kind == "cost_center":
            cost_center_form = CostCenterForm(request.POST, organization=request.organization)
            if cost_center_form.is_valid():
                cost_center = cost_center_form.save(commit=False)
                cost_center.organization = request.organization
                cost_center.full_clean()
                cost_center.save()
                messages.success(request, "Cost center added.")
                return redirect("policy_settings")
        elif kind == "category":
            category_form = ExpenseCategoryForm(request.POST, organization=request.organization)
            if category_form.is_valid():
                category = category_form.save(commit=False)
                category.organization = request.organization
                category.full_clean()
                category.save()
                messages.success(request, "Expense category added.")
                return redirect("policy_settings")
        else:
            messages.error(request, "Unknown settings action.")
    return render(
        request,
        "expenses/policy_settings.html",
        {
            "cost_centers": request.organization.cost_centers.select_related("manager"),
            "categories": request.organization.expense_categories.all(),
            "cost_center_form": cost_center_form,
            "category_form": category_form,
        },
    )


@workspace_required
def api_summary(request):
    reports = visible_reports(request)
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "currency": request.organization.base_currency,
            "role": request.membership.role,
            "reports": reports.count(),
            "submitted": reports.filter(status=ExpenseReport.Status.SUBMITTED).count(),
            "approved": reports.filter(status=ExpenseReport.Status.APPROVED).count(),
            "reimbursed": reports.filter(status=ExpenseReport.Status.REIMBURSED).count(),
            "visible_total": str(
                ExpenseItem.objects.filter(report__in=reports).aggregate(total=Sum("amount"))[
                    "total"
                ]
                or Decimal("0.00")
            ),
        }
    )


@workspace_required
def api_reports(request):
    reports = visible_reports(request)
    status = request.GET.get("status", "")
    if status in ExpenseReport.Status.values:
        reports = reports.filter(status=status)
    return JsonResponse(
        {
            "results": [
                {
                    "id": report.pk,
                    "reference": report.reference,
                    "title": report.title,
                    "submitter": report.submitter.username,
                    "cost_center": report.cost_center.code,
                    "status": report.status,
                    "total": str(report.total_amount),
                    "policy_issues": report.policy_issue_count,
                    "updated_at": report.updated_at,
                }
                for report in reports
            ]
        }
    )


@workspace_required
def api_report_detail(request, pk):
    report = get_visible_report(request, pk)
    return JsonResponse(
        {
            "id": report.pk,
            "reference": report.reference,
            "title": report.title,
            "purpose": report.purpose,
            "submitter": report.submitter.username,
            "status": report.status,
            "currency": request.organization.base_currency,
            "total": str(report.total_amount),
            "items": [
                {
                    "id": item.pk,
                    "date": item.expense_date,
                    "merchant": item.merchant,
                    "category": item.category.name,
                    "amount": str(item.amount),
                    "policy_note": item.policy_note,
                }
                for item in report.items.select_related("category")
            ],
        }
    )


@workspace_required
def api_policy(request):
    return JsonResponse(
        {
            "currency": request.organization.base_currency,
            "categories": [
                {
                    "name": category.name,
                    "daily_limit": str(category.daily_limit),
                    "receipt_required_over": str(category.receipt_required_over),
                    "active": category.active,
                }
                for category in request.organization.expense_categories.all()
            ],
            "cost_centers": [
                {
                    "code": cost_center.code,
                    "name": cost_center.name,
                    "active": cost_center.active,
                }
                for cost_center in request.organization.cost_centers.all()
            ],
        }
    )
