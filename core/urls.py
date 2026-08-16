from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("health/", views.health, name="health"),
    path("signup/", views.signup, name="signup"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("students/", views.students, name="students"),
    path("teachers/", views.teachers, name="teachers"),
    path("courses/", views.courses, name="courses"),
    path("attendance/", views.attendance, name="attendance"),
    path("invoices/", views.invoices, name="invoices"),
    path("invoices/<int:invoice_id>/payment/", views.record_payment, name="record_payment"),
]
