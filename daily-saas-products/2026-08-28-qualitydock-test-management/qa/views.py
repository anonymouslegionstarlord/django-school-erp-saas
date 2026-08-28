from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import (
    CommentForm,
    ExecutionUpdateForm,
    ProductForm,
    SignupForm,
    TestCaseForm,
    TestRunForm,
    TestSuiteForm,
)
from .models import Activity, Membership, Product, TestCase, TestExecution, TestRun


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
        messages.success(request, "Your quality workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def record_activity(run, actor, message):
    return Activity.objects.create(
        organization=run.organization, run=run, actor=actor, message=message
    )


@workspace_required
def dashboard(request):
    organization = request.organization
    products = Product.objects.filter(organization=organization)
    runs = TestRun.objects.filter(organization=organization).select_related("product", "created_by")
    executions = TestExecution.objects.filter(organization=organization)
    executed = executions.exclude(status=TestExecution.Status.NOT_RUN)
    passed = executed.filter(status=TestExecution.Status.PASSED).count()
    pass_rate = round(passed * 100 / executed.count()) if executed.exists() else 0
    product_health = []
    for product in products.filter(status=Product.Status.ACTIVE):
        latest_run = product.test_runs.filter(organization=organization).first()
        product_health.append(
            {
                "product": product,
                "case_count": TestCase.objects.filter(
                    organization=organization, suite__product=product, status=TestCase.Status.READY
                ).count(),
                "latest_run": latest_run,
            }
        )
    context = {
        "active_product_count": products.filter(status=Product.Status.ACTIVE).count(),
        "active_run_count": runs.exclude(status=TestRun.Status.COMPLETED).count(),
        "pass_rate": pass_rate,
        "critical_failure_count": executions.filter(
            status=TestExecution.Status.FAILED,
            test_case__priority=TestCase.Priority.CRITICAL,
            run__status__in=[TestRun.Status.PLANNED, TestRun.Status.IN_PROGRESS],
        ).count(),
        "recent_runs": runs[:6],
        "product_health": product_health,
        "my_queue": executions.filter(
            assigned_to=request.user,
            status=TestExecution.Status.NOT_RUN,
            run__status__in=[TestRun.Status.PLANNED, TestRun.Status.IN_PROGRESS],
        ).select_related("run", "test_case")[:6],
    }
    return render(request, "qa/dashboard.html", context)


@workspace_required
def product_list(request):
    products = Product.objects.filter(organization=request.organization).select_related("owner")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if query:
        products = products.filter(
            Q(key__icontains=query) | Q(name__icontains=query) | Q(description__icontains=query)
        )
    if status in Product.Status.values:
        products = products.filter(status=status)
    return render(
        request,
        "qa/product_list.html",
        {
            "products": products,
            "query": query,
            "status": status,
            "statuses": Product.Status.choices,
        },
    )


@workspace_required
def product_create(request):
    if not request.membership.can_manage:
        return HttpResponseForbidden("Only owners and QA leads can create products.")
    form = ProductForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        product = form.save(commit=False)
        product.organization = request.organization
        product.full_clean()
        product.save()
        messages.success(request, "Product added to the quality portfolio.")
        return redirect("product_detail", pk=product.pk)
    return render(request, "qa/product_form.html", {"form": form})


@workspace_required
def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related("owner"), pk=pk, organization=request.organization
    )
    cases = TestCase.objects.filter(
        organization=request.organization, suite__product=product
    ).select_related("suite")
    runs = TestRun.objects.filter(
        organization=request.organization, product=product
    ).select_related("created_by")
    return render(
        request,
        "qa/product_detail.html",
        {
            "product": product,
            "suites": product.test_suites.filter(organization=request.organization),
            "case_count": cases.count(),
            "ready_count": cases.filter(status=TestCase.Status.READY).count(),
            "critical_count": cases.filter(priority=TestCase.Priority.CRITICAL).count(),
            "recent_cases": cases[:8],
            "runs": runs[:6],
            "suite_form": TestSuiteForm(organization=request.organization, product=product),
        },
    )


@workspace_required
@require_POST
def suite_add(request, pk):
    if not request.membership.can_manage:
        return HttpResponseForbidden("Only owners and QA leads can create test suites.")
    product = get_object_or_404(Product, pk=pk, organization=request.organization)
    form = TestSuiteForm(request.POST, organization=request.organization, product=product)
    if form.is_valid() and form.cleaned_data["product"] == product:
        suite = form.save(commit=False)
        suite.organization = request.organization
        suite.full_clean()
        suite.save()
        messages.success(request, "Test suite created.")
    else:
        messages.error(request, "Please correct the test suite details.")
    return redirect("product_detail", pk=pk)


@workspace_required
def case_list(request):
    cases = TestCase.objects.filter(organization=request.organization).select_related(
        "suite__product", "created_by"
    )
    query = request.GET.get("q", "").strip()
    product_id = request.GET.get("product", "")
    priority = request.GET.get("priority", "")
    status = request.GET.get("status", "")
    if query:
        cases = cases.filter(
            Q(case_key__icontains=query)
            | Q(title__icontains=query)
            | Q(requirement_reference__icontains=query)
            | Q(steps__icontains=query)
        )
    if product_id.isdigit():
        cases = cases.filter(suite__product_id=product_id)
    if priority in TestCase.Priority.values:
        cases = cases.filter(priority=priority)
    if status in TestCase.Status.values:
        cases = cases.filter(status=status)
    return render(
        request,
        "qa/case_list.html",
        {
            "cases": cases,
            "query": query,
            "product_id": product_id,
            "priority": priority,
            "status": status,
            "products": request.organization.products.all(),
            "priorities": TestCase.Priority.choices,
            "statuses": TestCase.Status.choices,
        },
    )


@workspace_required
def case_create(request):
    if not request.membership.can_manage:
        return HttpResponseForbidden("Only owners and QA leads can author test cases.")
    product = None
    product_id = request.GET.get("product", "")
    if product_id.isdigit():
        product = get_object_or_404(Product, pk=product_id, organization=request.organization)
    form = TestCaseForm(request.POST or None, organization=request.organization, product=product)
    if request.method == "POST" and form.is_valid():
        test_case = form.save(commit=False)
        test_case.organization = request.organization
        test_case.created_by = request.user
        test_case.full_clean()
        test_case.save()
        messages.success(request, "Test case created.")
        return redirect("case_detail", pk=test_case.pk)
    return render(request, "qa/case_form.html", {"form": form, "test_case": None})


@workspace_required
def case_detail(request, pk):
    test_case = get_object_or_404(
        TestCase.objects.select_related("suite__product", "created_by"),
        pk=pk,
        organization=request.organization,
    )
    history = test_case.executions.filter(organization=request.organization).select_related(
        "run", "assigned_to"
    )[:10]
    return render(request, "qa/case_detail.html", {"test_case": test_case, "history": history})


@workspace_required
def case_edit(request, pk):
    if not request.membership.can_manage:
        return HttpResponseForbidden("Only owners and QA leads can edit test cases.")
    test_case = get_object_or_404(TestCase, pk=pk, organization=request.organization)
    form = TestCaseForm(request.POST or None, instance=test_case, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        test_case = form.save(commit=False)
        test_case.full_clean()
        test_case.save()
        messages.success(request, "Test case updated.")
        return redirect("case_detail", pk=pk)
    return render(request, "qa/case_form.html", {"form": form, "test_case": test_case})


@workspace_required
def run_list(request):
    runs = TestRun.objects.filter(organization=request.organization).select_related(
        "product", "created_by"
    )
    query = request.GET.get("q", "").strip()
    product_id = request.GET.get("product", "")
    status = request.GET.get("status", "")
    if query:
        runs = runs.filter(
            Q(name__icontains=query)
            | Q(target_version__icontains=query)
            | Q(product__name__icontains=query)
        )
    if product_id.isdigit():
        runs = runs.filter(product_id=product_id)
    if status in TestRun.Status.values:
        runs = runs.filter(status=status)
    return render(
        request,
        "qa/run_list.html",
        {
            "runs": runs,
            "query": query,
            "product_id": product_id,
            "status": status,
            "products": request.organization.products.all(),
            "statuses": TestRun.Status.choices,
        },
    )


@workspace_required
def run_create(request):
    if not request.membership.can_manage:
        return HttpResponseForbidden("Only owners and QA leads can create test runs.")
    form = TestRunForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            run = form.save(commit=False)
            run.organization = request.organization
            run.created_by = request.user
            run.full_clean()
            run.save()
            added = 0
            if form.cleaned_data["include_ready_cases"]:
                cases = TestCase.objects.filter(
                    organization=request.organization,
                    suite__product=run.product,
                    status=TestCase.Status.READY,
                )
                executions = [
                    TestExecution(
                        organization=request.organization,
                        run=run,
                        test_case=test_case,
                    )
                    for test_case in cases
                ]
                TestExecution.objects.bulk_create(executions, ignore_conflicts=True)
                added = len(executions)
            record_activity(run, request.user, f"Test run created with {added} ready case(s)")
        messages.success(request, "Test run created.")
        return redirect("run_detail", pk=run.pk)
    return render(request, "qa/run_form.html", {"form": form})


@workspace_required
def run_detail(request, pk):
    run = get_object_or_404(
        TestRun.objects.select_related("product", "created_by"),
        pk=pk,
        organization=request.organization,
    )
    executions = run.executions.filter(organization=request.organization).select_related(
        "test_case__suite", "assigned_to"
    )
    status = request.GET.get("status", "")
    assignee = request.GET.get("assignee", "")
    if status in TestExecution.Status.values:
        executions = executions.filter(status=status)
    if assignee == "unassigned":
        executions = executions.filter(assigned_to__isnull=True)
    elif assignee.isdigit():
        executions = executions.filter(assigned_to_id=assignee)
    rows = [
        {
            "execution": execution,
            "form": ExecutionUpdateForm(instance=execution, organization=request.organization),
        }
        for execution in executions
    ]
    assignees = request.organization.memberships.exclude(
        role=Membership.Role.VIEWER
    ).select_related("user")
    return render(
        request,
        "qa/run_detail.html",
        {
            "run": run,
            "rows": rows,
            "activities": run.activities.select_related("actor")[:25],
            "comment_form": CommentForm(),
            "execution_statuses": TestExecution.Status.choices,
            "status": status,
            "assignee": assignee,
            "assignees": assignees,
        },
    )


@workspace_required
@require_POST
def run_add_cases(request, pk):
    if not request.membership.can_manage:
        return HttpResponseForbidden("Only owners and QA leads can change run scope.")
    run = get_object_or_404(TestRun, pk=pk, organization=request.organization)
    if run.status == TestRun.Status.COMPLETED:
        messages.error(request, "A completed run cannot accept more cases.")
        return redirect("run_detail", pk=pk)
    existing = set(run.executions.values_list("test_case_id", flat=True))
    cases = TestCase.objects.filter(
        organization=request.organization,
        suite__product=run.product,
        status=TestCase.Status.READY,
    ).exclude(pk__in=existing)
    executions = [
        TestExecution(organization=request.organization, run=run, test_case=test_case)
        for test_case in cases
    ]
    TestExecution.objects.bulk_create(executions, ignore_conflicts=True)
    record_activity(run, request.user, f"Added {len(executions)} ready case(s) to scope")
    messages.success(request, f"Added {len(executions)} new case(s).")
    return redirect("run_detail", pk=pk)


@workspace_required
@require_POST
def run_start(request, pk):
    if not request.membership.can_manage:
        return HttpResponseForbidden("Only owners and QA leads can start a run.")
    run = get_object_or_404(TestRun, pk=pk, organization=request.organization)
    if run.status != TestRun.Status.PLANNED:
        messages.error(request, "Only a planned run can be started.")
        return redirect("run_detail", pk=pk)
    run.status = TestRun.Status.IN_PROGRESS
    if run.start_date is None:
        run.start_date = timezone.localdate()
    run.save(update_fields=["status", "start_date", "updated_at"])
    record_activity(run, request.user, "Test execution started")
    messages.success(request, "Run is now in progress.")
    return redirect("run_detail", pk=pk)


@workspace_required
@require_POST
def run_complete(request, pk):
    if not request.membership.can_manage:
        return HttpResponseForbidden("Only owners and QA leads can complete a run.")
    run = get_object_or_404(TestRun, pk=pk, organization=request.organization)
    if run.status != TestRun.Status.IN_PROGRESS:
        messages.error(request, "Only an in-progress run can be completed.")
        return redirect("run_detail", pk=pk)
    if (
        not run.executions.exists()
        or run.executions.filter(status=TestExecution.Status.NOT_RUN).exists()
    ):
        messages.error(request, "Resolve every not-run execution before completing the run.")
        return redirect("run_detail", pk=pk)
    run.status = TestRun.Status.COMPLETED
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "completed_at", "updated_at"])
    record_activity(run, request.user, f"Run completed at {run.pass_rate}% pass rate")
    messages.success(request, "Run completed and release metrics frozen.")
    return redirect("run_detail", pk=pk)


@workspace_required
@require_POST
def execution_update(request, run_pk, pk):
    execution = get_object_or_404(
        TestExecution.objects.select_related("run", "test_case", "assigned_to"),
        pk=pk,
        run_id=run_pk,
        organization=request.organization,
    )
    if not request.membership.can_execute:
        return HttpResponseForbidden("Viewer accounts cannot update test execution.")
    if (
        request.membership.role == Membership.Role.TESTER
        and execution.assigned_to_id != request.user.id
    ):
        return HttpResponseForbidden("Testers can update only executions assigned to them.")
    if execution.run.status == TestRun.Status.COMPLETED:
        return HttpResponseForbidden("Completed runs are read-only.")
    previous_status = execution.status
    form = ExecutionUpdateForm(request.POST, instance=execution, organization=request.organization)
    if form.is_valid():
        with transaction.atomic():
            execution = form.save()
            if execution.run.status == TestRun.Status.PLANNED:
                execution.run.status = TestRun.Status.IN_PROGRESS
                execution.run.start_date = execution.run.start_date or timezone.localdate()
                execution.run.save(update_fields=["status", "start_date", "updated_at"])
            message = (
                f"{execution.test_case.case_key} moved from "
                f"{dict(TestExecution.Status.choices)[previous_status]} to "
                f"{execution.get_status_display()}"
            )
            record_activity(execution.run, request.user, message)
        messages.success(request, "Execution result saved.")
    else:
        error = next(iter(form.errors.values()))[0]
        messages.error(request, f"Execution was not updated: {error}")
    return redirect("run_detail", pk=run_pk)


@workspace_required
@require_POST
def run_comment(request, pk):
    run = get_object_or_404(TestRun, pk=pk, organization=request.organization)
    if not request.membership.can_execute:
        return HttpResponseForbidden("Viewer accounts cannot add run comments.")
    form = CommentForm(request.POST)
    if form.is_valid():
        record_activity(run, request.user, form.cleaned_data["message"])
        messages.success(request, "Run comment added.")
    return redirect("run_detail", pk=pk)


@workspace_required
def api_summary(request):
    executions = TestExecution.objects.filter(organization=request.organization)
    executed = executions.exclude(status=TestExecution.Status.NOT_RUN)
    passed = executed.filter(status=TestExecution.Status.PASSED).count()
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "role": request.membership.role,
            "products": Product.objects.filter(organization=request.organization).count(),
            "test_cases": TestCase.objects.filter(organization=request.organization).count(),
            "active_runs": TestRun.objects.filter(organization=request.organization)
            .exclude(status=TestRun.Status.COMPLETED)
            .count(),
            "pass_rate": round(passed * 100 / executed.count()) if executed.exists() else 0,
            "critical_failures": executions.filter(
                status=TestExecution.Status.FAILED,
                test_case__priority=TestCase.Priority.CRITICAL,
            ).count(),
        }
    )


@workspace_required
def api_products(request):
    products = Product.objects.filter(organization=request.organization).select_related("owner")
    return JsonResponse(
        {
            "results": [
                {
                    "id": product.pk,
                    "key": product.key,
                    "name": product.name,
                    "status": product.status,
                    "owner": product.owner.username,
                    "test_cases": TestCase.objects.filter(
                        organization=request.organization, suite__product=product
                    ).count(),
                    "test_runs": product.test_runs.filter(
                        organization=request.organization
                    ).count(),
                }
                for product in products
            ]
        }
    )


@workspace_required
def api_cases(request):
    cases = TestCase.objects.filter(organization=request.organization).select_related(
        "suite__product"
    )
    product_id = request.GET.get("product", "")
    if product_id.isdigit():
        cases = cases.filter(suite__product_id=product_id)
    return JsonResponse(
        {
            "results": [
                {
                    "id": test_case.pk,
                    "key": test_case.case_key,
                    "title": test_case.title,
                    "product": test_case.suite.product.key,
                    "suite": test_case.suite.name,
                    "priority": test_case.priority,
                    "type": test_case.test_type,
                    "status": test_case.status,
                    "requirement": test_case.requirement_reference,
                }
                for test_case in cases
            ]
        }
    )


@workspace_required
def api_runs(request):
    runs = TestRun.objects.filter(organization=request.organization).select_related("product")
    status = request.GET.get("status", "")
    if status in TestRun.Status.values:
        runs = runs.filter(status=status)
    return JsonResponse(
        {
            "results": [
                {
                    "id": run.pk,
                    "reference": run.reference,
                    "name": run.name,
                    "product": run.product.key,
                    "version": run.target_version,
                    "environment": run.environment,
                    "status": run.status,
                    "completion_rate": run.completion_rate,
                    "pass_rate": run.pass_rate,
                    "failed": run.failed_count,
                    "blocked": run.blocked_count,
                }
                for run in runs
            ]
        }
    )


@workspace_required
def api_run_detail(request, pk):
    run = get_object_or_404(
        TestRun.objects.select_related("product"), pk=pk, organization=request.organization
    )
    return JsonResponse(
        {
            "id": run.pk,
            "reference": run.reference,
            "name": run.name,
            "product": run.product.key,
            "version": run.target_version,
            "status": run.status,
            "completion_rate": run.completion_rate,
            "pass_rate": run.pass_rate,
            "executions": [
                {
                    "id": execution.pk,
                    "case": execution.test_case.case_key,
                    "title": execution.test_case.title,
                    "status": execution.status,
                    "assignee": (execution.assigned_to.username if execution.assigned_to else None),
                    "defect": execution.defect_reference,
                    "executed_at": execution.executed_at,
                }
                for execution in run.executions.filter(
                    organization=request.organization
                ).select_related("test_case", "assigned_to")
            ],
        }
    )
