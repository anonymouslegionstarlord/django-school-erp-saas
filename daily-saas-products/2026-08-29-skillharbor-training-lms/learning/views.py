from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.db.models import Avg, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import (
    CommentForm,
    CourseForm,
    EnrollmentForm,
    GradeForm,
    ModuleForm,
    ProgressForm,
    SignupForm,
)
from .models import Activity, Course, Enrollment, LessonProgress, Membership, Module


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
        messages.success(request, "Your SkillHarbor workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def visible_courses(request):
    courses = Course.objects.filter(organization=request.organization).select_related("instructor")
    if request.membership.can_manage:
        return courses
    if request.membership.role == Membership.Role.INSTRUCTOR:
        return courses.filter(
            Q(instructor=request.user) | Q(status=Course.Status.PUBLISHED)
        ).distinct()
    return courses.filter(
        status=Course.Status.PUBLISHED, enrollments__learner=request.user
    ).distinct()


def visible_enrollments(request):
    enrollments = Enrollment.objects.filter(organization=request.organization).select_related(
        "course", "course__instructor", "learner", "assigned_by"
    )
    if request.membership.can_manage:
        return enrollments
    if request.membership.role == Membership.Role.INSTRUCTOR:
        return enrollments.filter(course__instructor=request.user)
    return enrollments.filter(learner=request.user)


def can_manage_course(request, course):
    return request.membership.can_manage or (
        request.membership.role == Membership.Role.INSTRUCTOR
        and course.instructor_id == request.user.id
    )


def record_activity(enrollment, actor, message):
    Activity.objects.create(
        organization=enrollment.organization,
        enrollment=enrollment,
        actor=actor,
        message=message,
    )


@workspace_required
def dashboard(request):
    enrollments = visible_enrollments(request)
    courses = visible_courses(request)
    total = enrollments.count()
    completed = enrollments.filter(status=Enrollment.Status.COMPLETED).count()
    overdue = sum(1 for enrollment in enrollments if enrollment.is_overdue)
    average_score = enrollments.filter(score__isnull=False).aggregate(value=Avg("score"))["value"]
    mandatory = enrollments.filter(course__mandatory=True)
    mandatory_total = mandatory.count()
    mandatory_completed = mandatory.filter(status=Enrollment.Status.COMPLETED).count()
    context = {
        "course_count": courses.count(),
        "enrollment_count": total,
        "in_progress_count": enrollments.filter(status=Enrollment.Status.IN_PROGRESS).count(),
        "completed_count": completed,
        "overdue_count": overdue,
        "completion_rate": round(completed * 100 / total) if total else 0,
        "average_score": round(average_score) if average_score is not None else None,
        "mandatory_rate": (
            round(mandatory_completed * 100 / mandatory_total) if mandatory_total else 0
        ),
        "recent_enrollments": enrollments[:6],
        "featured_courses": courses.filter(status=Course.Status.PUBLISHED)[:4],
    }
    return render(request, "learning/dashboard.html", context)


@workspace_required
def course_list(request):
    courses = visible_courses(request)
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    status = request.GET.get("status", "")
    if query:
        courses = courses.filter(
            Q(title__icontains=query) | Q(code__icontains=query) | Q(summary__icontains=query)
        )
    if category in Course.Category.values:
        courses = courses.filter(category=category)
    if status in Course.Status.values:
        courses = courses.filter(status=status)
    return render(
        request,
        "learning/course_list.html",
        {
            "courses": courses,
            "query": query,
            "category": category,
            "status": status,
            "categories": Course.Category.choices,
            "statuses": Course.Status.choices,
        },
    )


@workspace_required
def course_create(request):
    if not request.membership.can_author:
        return HttpResponseForbidden("Learners cannot create courses.")
    form = CourseForm(
        request.POST or None,
        organization=request.organization,
        user=request.user,
        initial={"status": Course.Status.DRAFT},
    )
    if request.method == "POST" and form.is_valid():
        course = form.save(commit=False)
        course.organization = request.organization
        course.full_clean()
        course.save()
        messages.success(request, "Course created. Add a module before publishing.")
        return redirect("course_detail", pk=course.pk)
    return render(request, "learning/course_form.html", {"form": form})


@workspace_required
def course_detail(request, pk):
    course = get_object_or_404(visible_courses(request), pk=pk)
    manage_course = can_manage_course(request, course)
    enrollments = Enrollment.objects.filter(
        organization=request.organization, course=course
    ).select_related("learner")
    if not manage_course:
        enrollments = enrollments.filter(learner=request.user)
    return render(
        request,
        "learning/course_detail.html",
        {
            "course": course,
            "modules": course.modules.filter(organization=request.organization),
            "enrollments": enrollments[:10],
            "manage_course": manage_course,
        },
    )


@workspace_required
def course_edit(request, pk):
    course = get_object_or_404(Course, pk=pk, organization=request.organization)
    if not can_manage_course(request, course):
        return HttpResponseForbidden("Only managers or the assigned instructor can edit.")
    form = CourseForm(
        request.POST or None,
        instance=course,
        organization=request.organization,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        course = form.save(commit=False)
        course.full_clean()
        course.save()
        messages.success(request, "Course updated.")
        return redirect("course_detail", pk=course.pk)
    return render(request, "learning/course_form.html", {"form": form, "course": course})


@workspace_required
@require_POST
def course_publish(request, pk):
    course = get_object_or_404(Course, pk=pk, organization=request.organization)
    if not can_manage_course(request, course):
        return HttpResponseForbidden("Only managers or the assigned instructor can publish.")
    if course.status == Course.Status.ARCHIVED:
        messages.error(request, "An archived course cannot be published.")
    elif not course.modules.filter(organization=request.organization).exists():
        messages.error(request, "Add at least one module before publishing.")
    else:
        course.status = Course.Status.PUBLISHED
        course.save(update_fields=["status", "updated_at"])
        messages.success(request, "Course published and ready for assignment.")
    return redirect("course_detail", pk=pk)


@workspace_required
def module_create(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk, organization=request.organization)
    if not can_manage_course(request, course):
        return HttpResponseForbidden("Only managers or the assigned instructor can add modules.")
    initial = {
        "order": (course.modules.order_by("-order").values_list("order", flat=True).first() or 0)
        + 1
    }
    form = ModuleForm(request.POST or None, course=course, initial=initial)
    if request.method == "POST" and form.is_valid():
        module = form.save(commit=False)
        module.organization = request.organization
        module.course = course
        module.full_clean()
        module.save()
        messages.success(request, "Learning module added.")
        return redirect("course_detail", pk=course.pk)
    return render(request, "learning/module_form.html", {"form": form, "course": course})


@workspace_required
def module_edit(request, course_pk, pk):
    course = get_object_or_404(Course, pk=course_pk, organization=request.organization)
    if not can_manage_course(request, course):
        return HttpResponseForbidden("Only managers or the assigned instructor can edit modules.")
    module = get_object_or_404(Module, pk=pk, course=course, organization=request.organization)
    form = ModuleForm(request.POST or None, instance=module, course=course)
    if request.method == "POST" and form.is_valid():
        module = form.save(commit=False)
        module.full_clean()
        module.save()
        messages.success(request, "Learning module updated.")
        return redirect("course_detail", pk=course.pk)
    return render(
        request,
        "learning/module_form.html",
        {"form": form, "course": course, "module": module},
    )


@workspace_required
def enrollment_list(request):
    enrollments = visible_enrollments(request)
    query = request.GET.get("q", "").strip()
    course_id = request.GET.get("course", "")
    status = request.GET.get("status", "")
    overdue = request.GET.get("overdue", "")
    if query:
        enrollments = enrollments.filter(
            Q(learner__username__icontains=query)
            | Q(learner__first_name__icontains=query)
            | Q(course__title__icontains=query)
            | Q(course__code__icontains=query)
        )
    if course_id.isdigit():
        enrollments = enrollments.filter(course_id=course_id)
    if status in Enrollment.Status.values:
        enrollments = enrollments.filter(status=status)
    if overdue == "1":
        enrollments = enrollments.filter(due_date__lt=timezone.localdate()).exclude(
            status=Enrollment.Status.COMPLETED
        )
    return render(
        request,
        "learning/enrollment_list.html",
        {
            "enrollments": enrollments,
            "query": query,
            "course_id": course_id,
            "status": status,
            "overdue": overdue,
            "courses": visible_courses(request),
            "statuses": Enrollment.Status.choices,
        },
    )


@workspace_required
def enrollment_create(request):
    if not request.membership.can_author:
        return HttpResponseForbidden("Learners cannot assign courses.")
    form = EnrollmentForm(
        request.POST or None, organization=request.organization, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            enrollment = form.save(commit=False)
            enrollment.organization = request.organization
            enrollment.assigned_by = request.user
            enrollment.full_clean()
            enrollment.save()
            LessonProgress.objects.bulk_create(
                [
                    LessonProgress(
                        organization=request.organization,
                        enrollment=enrollment,
                        module=module,
                    )
                    for module in enrollment.course.modules.filter(
                        organization=request.organization
                    )
                ]
            )
            record_activity(
                enrollment,
                request.user,
                f"Course assigned with {enrollment.total_module_count} module(s)",
            )
        messages.success(request, "Course assigned to learner.")
        return redirect("enrollment_detail", pk=enrollment.pk)
    return render(request, "learning/enrollment_form.html", {"form": form})


@workspace_required
def enrollment_detail(request, pk):
    enrollment = get_object_or_404(visible_enrollments(request), pk=pk)
    progress_rows = enrollment.progress_records.filter(
        organization=request.organization
    ).select_related("module")
    can_grade = request.membership.can_manage or (
        request.membership.role == Membership.Role.INSTRUCTOR
        and enrollment.course.instructor_id == request.user.id
    )
    return render(
        request,
        "learning/enrollment_detail.html",
        {
            "enrollment": enrollment,
            "progress_rows": progress_rows,
            "progress_form": ProgressForm(),
            "grade_form": GradeForm(
                pass_mark=enrollment.course.pass_mark,
                initial={"score": enrollment.score},
            ),
            "comment_form": CommentForm(),
            "activities": enrollment.activities.select_related("actor")[:25],
            "can_grade": can_grade,
        },
    )


@workspace_required
@require_POST
def progress_update(request, enrollment_pk, pk):
    enrollment = get_object_or_404(visible_enrollments(request), pk=enrollment_pk)
    progress = get_object_or_404(
        LessonProgress,
        pk=pk,
        enrollment=enrollment,
        organization=request.organization,
    )
    if request.membership.role == Membership.Role.LEARNER:
        allowed = enrollment.learner_id == request.user.id
    else:
        allowed = request.membership.can_manage or (
            request.membership.role == Membership.Role.INSTRUCTOR
            and enrollment.course.instructor_id == request.user.id
        )
    if not allowed:
        return HttpResponseForbidden("You cannot update this learner's progress.")
    if enrollment.status == Enrollment.Status.COMPLETED:
        return HttpResponseForbidden("Completed enrollments are read-only.")
    form = ProgressForm(request.POST)
    if form.is_valid():
        was_completed = progress.completed
        progress.completed = form.cleaned_data["completed"]
        progress.learner_note = form.cleaned_data["learner_note"]
        progress.full_clean()
        progress.save()
        if progress.completed and enrollment.status == Enrollment.Status.ASSIGNED:
            enrollment.status = Enrollment.Status.IN_PROGRESS
            enrollment.started_at = timezone.now()
            enrollment.save(update_fields=["status", "started_at", "updated_at"])
        action = "completed" if progress.completed else "reopened"
        if progress.completed != was_completed:
            record_activity(enrollment, request.user, f"{progress.module.title} marked {action}")
        messages.success(request, "Module progress saved.")
    else:
        messages.error(request, "Progress could not be saved.")
    return redirect("enrollment_detail", pk=enrollment.pk)


@workspace_required
@require_POST
def enrollment_grade(request, pk):
    enrollment = get_object_or_404(visible_enrollments(request), pk=pk)
    allowed = request.membership.can_manage or (
        request.membership.role == Membership.Role.INSTRUCTOR
        and enrollment.course.instructor_id == request.user.id
    )
    if not allowed:
        return HttpResponseForbidden("Only managers or the course instructor can grade.")
    if enrollment.status == Enrollment.Status.COMPLETED:
        return HttpResponseForbidden("Completed enrollments are read-only.")
    form = GradeForm(request.POST, pass_mark=enrollment.course.pass_mark)
    if form.is_valid():
        if (
            enrollment.total_module_count == 0
            or enrollment.completed_module_count != enrollment.total_module_count
        ):
            messages.error(request, "Complete every module before recording the final score.")
            return redirect("enrollment_detail", pk=pk)
        enrollment.score = form.cleaned_data["score"]
        passed = enrollment.score >= enrollment.course.pass_mark
        enrollment.status = Enrollment.Status.COMPLETED if passed else Enrollment.Status.IN_PROGRESS
        enrollment.completed_at = timezone.now() if passed else None
        if enrollment.started_at is None:
            enrollment.started_at = timezone.now()
        enrollment.save(
            update_fields=[
                "score",
                "status",
                "completed_at",
                "started_at",
                "updated_at",
            ]
        )
        result = "passed and completed" if passed else "did not meet the pass mark"
        note = form.cleaned_data["note"].strip()
        message = f"Final score {enrollment.score}% — {result}"
        if note:
            message = f"{message}. Feedback: {note}"
        record_activity(enrollment, request.user, message)
        messages.success(request, f"Score recorded: {enrollment.score}%.")
    else:
        error = next(iter(form.errors.values()))[0]
        messages.error(request, f"Score was not saved: {error}")
    return redirect("enrollment_detail", pk=pk)


@workspace_required
@require_POST
def enrollment_comment(request, pk):
    enrollment = get_object_or_404(visible_enrollments(request), pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        record_activity(enrollment, request.user, form.cleaned_data["message"])
        messages.success(request, "Learning note added.")
    return redirect("enrollment_detail", pk=pk)


@workspace_required
def api_summary(request):
    enrollments = visible_enrollments(request)
    total = enrollments.count()
    completed = enrollments.filter(status=Enrollment.Status.COMPLETED).count()
    scores = enrollments.filter(score__isnull=False).aggregate(value=Avg("score"))["value"]
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "role": request.membership.role,
            "courses": visible_courses(request).count(),
            "enrollments": total,
            "in_progress": enrollments.filter(status=Enrollment.Status.IN_PROGRESS).count(),
            "completed": completed,
            "overdue": sum(1 for enrollment in enrollments if enrollment.is_overdue),
            "completion_rate": round(completed * 100 / total) if total else 0,
            "average_score": round(scores) if scores is not None else None,
        }
    )


@workspace_required
def api_courses(request):
    courses = visible_courses(request)
    category = request.GET.get("category", "")
    if category in Course.Category.values:
        courses = courses.filter(category=category)
    return JsonResponse(
        {
            "results": [
                {
                    "id": course.pk,
                    "code": course.code,
                    "title": course.title,
                    "category": course.category,
                    "level": course.level,
                    "status": course.status,
                    "mandatory": course.mandatory,
                    "instructor": course.instructor.username,
                    "modules": course.modules.filter(organization=request.organization).count(),
                    "pass_mark": course.pass_mark,
                }
                for course in courses
            ]
        }
    )


@workspace_required
def api_enrollments(request):
    enrollments = visible_enrollments(request)
    status = request.GET.get("status", "")
    if status in Enrollment.Status.values:
        enrollments = enrollments.filter(status=status)
    return JsonResponse(
        {
            "results": [
                {
                    "id": enrollment.pk,
                    "reference": enrollment.reference,
                    "course": enrollment.course.code,
                    "learner": enrollment.learner.username,
                    "status": enrollment.status,
                    "overdue": enrollment.is_overdue,
                    "due_date": enrollment.due_date,
                    "progress": enrollment.progress_percent,
                    "score": enrollment.score,
                    "passed": enrollment.passed,
                }
                for enrollment in enrollments
            ]
        }
    )


@workspace_required
def api_enrollment_detail(request, pk):
    enrollment = get_object_or_404(visible_enrollments(request), pk=pk)
    return JsonResponse(
        {
            "id": enrollment.pk,
            "reference": enrollment.reference,
            "course": {
                "code": enrollment.course.code,
                "title": enrollment.course.title,
                "pass_mark": enrollment.course.pass_mark,
            },
            "learner": enrollment.learner.username,
            "status": enrollment.status,
            "due_date": enrollment.due_date,
            "overdue": enrollment.is_overdue,
            "progress": enrollment.progress_percent,
            "score": enrollment.score,
            "modules": [
                {
                    "id": progress.module_id,
                    "title": progress.module.title,
                    "order": progress.module.order,
                    "completed": progress.completed,
                    "completed_at": progress.completed_at,
                    "note": progress.learner_note,
                }
                for progress in enrollment.progress_records.filter(
                    organization=request.organization
                ).select_related("module")
            ],
        }
    )
