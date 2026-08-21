from django.urls import path
from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/schedule/", views.schedule, name="schedule"),
    path("app/services/", views.services, name="services"),
    path("app/customers/", views.customers, name="customers"),
    path("app/appointments/new/", views.create_appointment, name="create_appointment"),
    path("app/appointments/<int:pk>/", views.appointment_detail, name="appointment_detail"),
    path("app/appointments/<int:pk>/status/", views.update_status, name="update_status"),
    path("api/v1/summary/", views.api_summary, name="api_summary"),
    path("api/v1/appointments/", views.api_appointments, name="api_appointments"),
    path("api/v1/services/", views.api_services, name="api_services"),
]
