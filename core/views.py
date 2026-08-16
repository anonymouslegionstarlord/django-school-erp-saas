from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import school_required
from .forms import AttendanceForm, CourseForm, InvoiceForm, PaymentForm, SchoolSignUpForm, StudentForm, TeacherForm
from .models import Attendance, Course, Invoice, Membership, Payment, Student, Teacher

MANAGER_ROLES = {Membership.Role.OWNER, Membership.Role.ADMIN}
FINANCE_ROLES = MANAGER_ROLES | {Membership.Role.ACCOUNTANT}
ATTENDANCE_ROLES = MANAGER_ROLES | {Membership.Role.TEACHER}


def _can(request, roles):
    return bool(request.membership and request.membership.role in roles)


def landing(request):
    return render(request, "core/landing.html")


def health(request):
    return JsonResponse({"status": "ok", "service": "django-school-erp-saas"})


def signup(request):
    if request.user.is_authenticated and getattr(request, "school", None):
        return redirect("dashboard")
    form = SchoolSignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your school workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@school_required
def dashboard(request):
    school = request.school
    invoices = Invoice.objects.filter(school=school).select_related("student")
    for invoice in invoices.exclude(status=Invoice.Status.PAID):
        invoice.refresh_status()
    billed = invoices.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    paid = Payment.objects.filter(invoice__school=school).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    today_attendance = Attendance.objects.filter(school=school, date=timezone.localdate())
    context = {
        "student_count": Student.objects.filter(school=school, is_active=True).count(),
        "teacher_count": Teacher.objects.filter(school=school, is_active=True).count(),
        "course_count": Course.objects.filter(school=school, is_active=True).count(),
        "present_today": today_attendance.filter(status=Attendance.Status.PRESENT).count(),
        "attendance_total": today_attendance.count(),
        "billed": billed,
        "paid": paid,
        "outstanding": max(billed - paid, Decimal("0.00")),
        "recent_invoices": invoices[:5],
    }
    return render(request, "core/dashboard.html", context)


@school_required
def students(request):
    if request.method == "POST" and not _can(request, MANAGER_ROLES):
        return HttpResponseForbidden("Only owners and administrators can add students.")
    form = StudentForm(request.POST or None, school=request.school)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Student added successfully.")
        return redirect("students")
    query = request.GET.get("q", "").strip()
    records = Student.objects.filter(school=request.school)
    if query:
        records = records.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(admission_number__icontains=query)
            | Q(class_name__icontains=query)
        )
    return render(
        request,
        "core/students.html",
        {"form": form, "records": records, "query": query, "can_manage": _can(request, MANAGER_ROLES)},
    )


@school_required
def teachers(request):
    if request.method == "POST" and not _can(request, MANAGER_ROLES):
        return HttpResponseForbidden("Only owners and administrators can add teachers.")
    form = TeacherForm(request.POST or None, school=request.school)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Teacher added successfully.")
        return redirect("teachers")
    records = Teacher.objects.filter(school=request.school)
    return render(
        request, "core/teachers.html", {"form": form, "records": records, "can_manage": _can(request, MANAGER_ROLES)}
    )


@school_required
def courses(request):
    if request.method == "POST" and not _can(request, MANAGER_ROLES):
        return HttpResponseForbidden("Only owners and administrators can add courses.")
    form = CourseForm(request.POST or None, school=request.school)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Course added successfully.")
        return redirect("courses")
    records = Course.objects.filter(school=request.school).select_related("teacher")
    return render(
        request, "core/courses.html", {"form": form, "records": records, "can_manage": _can(request, MANAGER_ROLES)}
    )


@school_required
def attendance(request):
    if request.method == "POST" and not _can(request, ATTENDANCE_ROLES):
        return HttpResponseForbidden("Your role cannot mark attendance.")
    form = AttendanceForm(request.POST or None, school=request.school)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.marked_by = request.user
        record.save()
        messages.success(request, "Attendance recorded.")
        return redirect("attendance")
    records = Attendance.objects.filter(school=request.school).select_related("student", "course")[:100]
    return render(
        request,
        "core/attendance.html",
        {"form": form, "records": records, "can_manage": _can(request, ATTENDANCE_ROLES)},
    )


@school_required
def invoices(request):
    if request.method == "POST" and not _can(request, FINANCE_ROLES):
        return HttpResponseForbidden("Your role cannot create invoices.")
    form = InvoiceForm(request.POST or None, school=request.school)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Invoice created.")
        return redirect("invoices")
    records = Invoice.objects.filter(school=request.school).select_related("student")
    for invoice in records.exclude(status=Invoice.Status.PAID):
        invoice.refresh_status()
    return render(
        request,
        "core/invoices.html",
        {"form": form, "records": records, "can_manage": _can(request, FINANCE_ROLES)},
    )


@school_required
def record_payment(request, invoice_id):
    if not _can(request, FINANCE_ROLES):
        return HttpResponseForbidden("Your role cannot record payments.")
    invoice = get_object_or_404(Invoice, pk=invoice_id, school=request.school)
    form = PaymentForm(request.POST or None, initial={"amount": invoice.balance, "paid_at": timezone.localtime()})
    if request.method == "POST" and form.is_valid():
        payment = form.save(commit=False)
        if payment.amount > invoice.balance:
            form.add_error("amount", "Payment cannot exceed the outstanding balance.")
        else:
            payment.invoice = invoice
            payment.recorded_by = request.user
            payment.save()
            messages.success(request, "Payment recorded successfully.")
            return redirect("invoices")
    return render(request, "core/payment_form.html", {"form": form, "invoice": invoice})
