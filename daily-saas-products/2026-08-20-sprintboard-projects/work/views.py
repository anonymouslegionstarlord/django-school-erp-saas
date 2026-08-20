from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import CommentForm, ProjectForm, SignupForm, TaskForm
from .models import Project, Task


def landing(request):
    return redirect("dashboard") if request.user.is_authenticated else render(request, "work/landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your SprintBoard workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@workspace_required
def dashboard(request):
    tasks = Task.objects.filter(organization=request.organization).select_related("project", "assignee")
    active = tasks.exclude(status=Task.Status.DONE)
    context = {
        "project_count": Project.objects.filter(organization=request.organization, archived=False).count(),
        "active_count": active.count(),
        "done_count": tasks.filter(status=Task.Status.DONE).count(),
        "overdue_count": active.filter(due_date__lt=timezone.localdate()).count(),
        "my_tasks": active.filter(assignee=request.user)[:6],
        "recent_tasks": tasks[:7],
        "status_counts": [(label, tasks.filter(status=value).count()) for value, label in Task.Status.choices],
    }
    return render(request, "work/dashboard.html", context)


@workspace_required
def projects(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        p = form.save(commit=False)
        p.organization = request.organization
        p.save()
        messages.success(request, "Project created.")
        return redirect("projects")
    rows = Project.objects.filter(organization=request.organization).annotate(
        task_count=Count("tasks"), done_count=Count("tasks", filter=Q(tasks__status=Task.Status.DONE))
    )
    return render(request, "work/projects.html", {"form": form, "projects": rows})


@workspace_required
def board(request):
    tasks = Task.objects.filter(organization=request.organization).select_related("project", "assignee")
    project_id = request.GET.get("project")
    if project_id:
        tasks = tasks.filter(project_id=project_id)
    columns = [(value, label, tasks.filter(status=value)) for value, label in Task.Status.choices]
    return render(
        request,
        "work/board.html",
        {
            "columns": columns,
            "projects": Project.objects.filter(organization=request.organization, archived=False),
            "selected_project": project_id,
        },
    )


@workspace_required
def create_task(request):
    form = TaskForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.organization = request.organization
        task.save()
        messages.success(request, "Task created.")
        return redirect("task_detail", pk=task.pk)
    return render(request, "work/task_form.html", {"form": form})


@workspace_required
def task_detail(request, pk):
    task = get_object_or_404(Task.objects.select_related("project", "assignee"), pk=pk, organization=request.organization)
    form = CommentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        c.task = task
        c.organization = request.organization
        c.author = request.user
        c.save()
        messages.success(request, "Comment added.")
        return redirect("task_detail", pk=pk)
    return render(request, "work/task_detail.html", {"task": task, "form": form})


@require_POST
@workspace_required
def update_task(request, pk):
    task = get_object_or_404(Task, pk=pk, organization=request.organization)
    status = request.POST.get("status")
    priority = request.POST.get("priority")
    if status in Task.Status.values:
        task.status = status
    if priority in Task.Priority.values:
        task.priority = priority
    task.save()
    messages.success(request, "Task updated.")
    return redirect(request.POST.get("next") or "board")


def task_payload(t):
    return {
        "id": t.id,
        "title": t.title,
        "project": t.project.code,
        "status": t.status,
        "priority": t.priority,
        "assignee": t.assignee.username if t.assignee else None,
        "due_date": t.due_date,
        "overdue": t.is_overdue,
    }


@workspace_required
def api_summary(request):
    tasks = Task.objects.filter(organization=request.organization)
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "projects": Project.objects.filter(organization=request.organization, archived=False).count(),
            "active_tasks": tasks.exclude(status="done").count(),
            "completed": tasks.filter(status="done").count(),
        }
    )


@workspace_required
def api_tasks(request):
    tasks = Task.objects.filter(organization=request.organization).select_related("project", "assignee")
    return JsonResponse({"results": [task_payload(t) for t in tasks]})


@workspace_required
def api_projects(request):
    return JsonResponse(
        {"results": list(Project.objects.filter(organization=request.organization).values("id", "name", "code", "color", "archived"))}
    )
