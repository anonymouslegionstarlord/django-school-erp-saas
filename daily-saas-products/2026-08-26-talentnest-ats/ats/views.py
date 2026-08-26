from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import (
    ActivityForm,
    ApplicationForm,
    ApplicationUpdateForm,
    CandidateForm,
    InterviewFeedbackForm,
    InterviewForm,
    JobForm,
    SignupForm,
)
from .models import Activity, Application, Candidate, Interview, JobOpening, Membership


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
        messages.success(request, "Your recruiting workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@workspace_required
def dashboard(request):
    jobs = JobOpening.objects.filter(organization=request.organization)
    applications = Application.objects.filter(organization=request.organization)
    interviews = Interview.objects.filter(organization=request.organization)
    today = timezone.localdate()
    month_start = today.replace(day=1)
    upcoming = interviews.filter(
        status=Interview.Status.SCHEDULED,
        scheduled_at__gte=timezone.now(),
        scheduled_at__lte=timezone.now() + timedelta(days=7),
    ).select_related("application__candidate", "application__job", "interviewer")
    context = {
        "open_jobs": jobs.filter(status=JobOpening.Status.OPEN).count(),
        "active_applications": applications.exclude(
            stage__in=[Application.Stage.HIRED, Application.Stage.REJECTED]
        ).count(),
        "candidate_count": Candidate.objects.filter(organization=request.organization).count(),
        "hires_this_month": applications.filter(
            stage=Application.Stage.HIRED, updated_at__date__gte=month_start
        ).count(),
        "pipeline_counts": [
            (value, label, applications.filter(stage=value).count())
            for value, label in Application.Stage.choices
        ],
        "upcoming_interviews": upcoming[:6],
        "recent_applications": applications.select_related("candidate", "job", "owner")[:6],
    }
    return render(request, "ats/dashboard.html", context)


@workspace_required
def job_list(request):
    jobs = JobOpening.objects.filter(organization=request.organization).select_related("recruiter")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if query:
        jobs = jobs.filter(
            Q(title__icontains=query)
            | Q(code__icontains=query)
            | Q(department__icontains=query)
            | Q(location__icontains=query)
        )
    if status in JobOpening.Status.values:
        jobs = jobs.filter(status=status)
    return render(
        request,
        "ats/job_list.html",
        {
            "jobs": jobs,
            "query": query,
            "status": status,
            "statuses": JobOpening.Status.choices,
        },
    )


@workspace_required
def job_create(request):
    if not request.membership.can_manage:
        messages.error(request, "Interviewer accounts cannot create job openings.")
        return redirect("job_list")
    form = JobForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.organization = request.organization
        job.save()
        messages.success(request, "Job opening created.")
        return redirect("job_detail", pk=job.pk)
    return render(request, "ats/job_form.html", {"form": form})


@workspace_required
def job_detail(request, pk):
    job = get_object_or_404(
        JobOpening.objects.select_related("recruiter"), pk=pk, organization=request.organization
    )
    applications = job.applications.filter(organization=request.organization).select_related(
        "candidate", "owner"
    )
    return render(
        request,
        "ats/job_detail.html",
        {
            "job": job,
            "applications": applications,
            "stage_counts": [
                (label, applications.filter(stage=value).count())
                for value, label in Application.Stage.choices
            ],
        },
    )


@workspace_required
def candidate_list(request):
    candidates = Candidate.objects.filter(organization=request.organization)
    query = request.GET.get("q", "").strip()
    if query:
        candidates = candidates.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(skills__icontains=query)
            | Q(current_company__icontains=query)
        )
    form = CandidateForm(request.POST or None, organization=request.organization)
    if request.method == "POST":
        if not request.membership.can_manage:
            return JsonResponse({"detail": "Forbidden"}, status=403)
        if form.is_valid():
            candidate = form.save(commit=False)
            candidate.organization = request.organization
            candidate.save()
            messages.success(request, "Candidate added.")
            return redirect("candidate_list")
    return render(
        request,
        "ats/candidate_list.html",
        {"candidates": candidates, "query": query, "form": form},
    )


@workspace_required
def pipeline(request):
    applications = Application.objects.filter(organization=request.organization).select_related(
        "candidate", "job", "owner"
    )
    job_id = request.GET.get("job", "")
    query = request.GET.get("q", "").strip()
    if job_id.isdigit():
        applications = applications.filter(job_id=job_id)
    if query:
        applications = applications.filter(
            Q(candidate__name__icontains=query)
            | Q(candidate__email__icontains=query)
            | Q(job__title__icontains=query)
        )
    application_rows = list(applications)
    columns = [
        (value, label, [item for item in application_rows if item.stage == value])
        for value, label in Application.Stage.choices
    ]
    return render(
        request,
        "ats/pipeline.html",
        {
            "columns": columns,
            "jobs": request.organization.job_openings.all(),
            "job_id": job_id,
            "query": query,
        },
    )


@workspace_required
def application_create(request):
    if not request.membership.can_manage:
        messages.error(request, "Interviewer accounts cannot create applications.")
        return redirect("pipeline")
    initial = {}
    if request.GET.get("job", "").isdigit():
        initial["job"] = request.GET["job"]
    form = ApplicationForm(request.POST or None, organization=request.organization, initial=initial)
    if request.method == "POST" and form.is_valid():
        application = form.save(commit=False)
        application.organization = request.organization
        application.save()
        Activity.objects.create(
            organization=request.organization,
            application=application,
            author=request.user,
            message=f"Application created in {application.get_stage_display()}",
        )
        messages.success(request, "Application added to the pipeline.")
        return redirect("application_detail", pk=application.pk)
    return render(request, "ats/application_form.html", {"form": form})


@workspace_required
def application_detail(request, pk):
    application = get_object_or_404(
        Application.objects.select_related("candidate", "job", "owner"),
        pk=pk,
        organization=request.organization,
    )
    interviews = application.interviews.filter(organization=request.organization).select_related(
        "interviewer"
    )
    return render(
        request,
        "ats/application_detail.html",
        {
            "application": application,
            "interviews": interviews,
            "activities": application.activities.select_related("author")[:20],
            "update_form": ApplicationUpdateForm(
                instance=application, organization=request.organization
            ),
            "interview_form": InterviewForm(
                organization=request.organization, application=application
            ),
            "activity_form": ActivityForm(),
        },
    )


@workspace_required
@require_POST
def application_update(request, pk):
    application = get_object_or_404(Application, pk=pk, organization=request.organization)
    if not request.membership.can_manage:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    previous_stage = application.stage
    form = ApplicationUpdateForm(
        request.POST, instance=application, organization=request.organization
    )
    if form.is_valid():
        application = form.save()
        message = "Application details updated"
        if application.stage != previous_stage:
            message = f"Moved to {application.get_stage_display()}"
        Activity.objects.create(
            organization=request.organization,
            application=application,
            author=request.user,
            message=message,
        )
        messages.success(request, "Application updated.")
    else:
        messages.error(request, "Please correct the application form.")
    return redirect("application_detail", pk=pk)


@workspace_required
@require_POST
def interview_add(request, pk):
    application = get_object_or_404(Application, pk=pk, organization=request.organization)
    if not request.membership.can_manage:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    form = InterviewForm(request.POST, organization=request.organization, application=application)
    if form.is_valid():
        interview = form.save(commit=False)
        interview.organization = request.organization
        interview.application = application
        interview.save()
        if application.stage in [Application.Stage.APPLIED, Application.Stage.SCREENING]:
            application.stage = Application.Stage.INTERVIEW
            application.save(update_fields=["stage", "updated_at"])
        Activity.objects.create(
            organization=request.organization,
            application=application,
            author=request.user,
            message=f"Interview scheduled with {interview.interviewer.username}",
        )
        messages.success(request, "Interview scheduled.")
    else:
        messages.error(request, "Please correct the interview form.")
    return redirect("application_detail", pk=pk)


@workspace_required
@require_POST
def interview_feedback(request, pk):
    interview = get_object_or_404(
        Interview.objects.select_related("application"),
        pk=pk,
        organization=request.organization,
    )
    if not request.membership.can_manage and interview.interviewer_id != request.user.id:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    form = InterviewFeedbackForm(request.POST, instance=interview)
    if form.is_valid():
        interview = form.save()
        Activity.objects.create(
            organization=request.organization,
            application=interview.application,
            author=request.user,
            message=f"Interview marked {interview.get_status_display().lower()}",
        )
        messages.success(request, "Interview feedback saved.")
    else:
        messages.error(request, "Completed interviews require both a score and feedback.")
    return redirect("application_detail", pk=interview.application_id)


@workspace_required
@require_POST
def activity_add(request, pk):
    application = get_object_or_404(Application, pk=pk, organization=request.organization)
    form = ActivityForm(request.POST)
    if form.is_valid():
        activity = form.save(commit=False)
        activity.organization = request.organization
        activity.application = application
        activity.author = request.user
        activity.save()
    return redirect("application_detail", pk=pk)


@workspace_required
def interview_list(request):
    interviews = Interview.objects.filter(organization=request.organization).select_related(
        "application__candidate", "application__job", "interviewer"
    )
    if request.membership.role == Membership.Role.INTERVIEWER:
        interviews = interviews.filter(interviewer=request.user)
    status = request.GET.get("status", "")
    if status in Interview.Status.values:
        interviews = interviews.filter(status=status)
    return render(
        request,
        "ats/interview_list.html",
        {"interviews": interviews, "status": status, "statuses": Interview.Status.choices},
    )


@workspace_required
def api_summary(request):
    applications = Application.objects.filter(organization=request.organization)
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "open_jobs": request.organization.job_openings.filter(
                status=JobOpening.Status.OPEN
            ).count(),
            "candidates": request.organization.candidates.count(),
            "active_applications": applications.exclude(
                stage__in=[Application.Stage.HIRED, Application.Stage.REJECTED]
            ).count(),
            "scheduled_interviews": request.organization.interviews.filter(
                status=Interview.Status.SCHEDULED, scheduled_at__gte=timezone.now()
            ).count(),
        }
    )


@workspace_required
def api_jobs(request):
    rows = JobOpening.objects.filter(organization=request.organization).select_related("recruiter")
    return JsonResponse(
        {
            "results": [
                {
                    "id": item.pk,
                    "code": item.code,
                    "title": item.title,
                    "department": item.department,
                    "location": item.location,
                    "status": item.status,
                    "openings": item.openings,
                    "recruiter": item.recruiter.username,
                }
                for item in rows
            ]
        }
    )


@workspace_required
def api_applications(request):
    rows = Application.objects.filter(organization=request.organization).select_related(
        "candidate", "job", "owner"
    )
    return JsonResponse(
        {
            "results": [
                {
                    "id": item.pk,
                    "candidate": item.candidate.name,
                    "job": item.job.code,
                    "stage": item.stage,
                    "rating": item.rating,
                    "owner": item.owner.username,
                    "updated_at": item.updated_at,
                }
                for item in rows
            ]
        }
    )


@workspace_required
def api_interviews(request):
    rows = Interview.objects.filter(organization=request.organization).select_related(
        "application__candidate", "application__job", "interviewer"
    )
    if request.membership.role == Membership.Role.INTERVIEWER:
        rows = rows.filter(interviewer=request.user)
    return JsonResponse(
        {
            "results": [
                {
                    "id": item.pk,
                    "candidate": item.application.candidate.name,
                    "job": item.application.job.code,
                    "interviewer": item.interviewer.username,
                    "scheduled_at": item.scheduled_at,
                    "mode": item.mode,
                    "status": item.status,
                    "score": item.score,
                }
                for item in rows
            ]
        }
    )
