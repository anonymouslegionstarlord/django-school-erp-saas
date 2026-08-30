from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("status/<slug:slug>/", views.public_status, name="public_status"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/services/", views.service_list, name="service_list"),
    path("app/services/new/", views.service_create, name="service_create"),
    path("app/services/<int:pk>/edit/", views.service_edit, name="service_edit"),
    path("app/incidents/", views.incident_list, name="incident_list"),
    path("app/incidents/new/", views.incident_create, name="incident_create"),
    path("app/incidents/<int:pk>/", views.incident_detail, name="incident_detail"),
    path("app/incidents/<int:pk>/updates/", views.incident_update, name="incident_update"),
    path(
        "app/incidents/<int:pk>/responders/",
        views.incident_responder_add,
        name="incident_responder_add",
    ),
    path(
        "app/incidents/<int:pk>/actions/",
        views.incident_action_add,
        name="incident_action_add",
    ),
    path(
        "app/incidents/<int:incident_pk>/actions/<int:pk>/toggle/",
        views.incident_action_toggle,
        name="incident_action_toggle",
    ),
    path("api/summary/", views.api_summary, name="api_summary"),
    path("api/services/", views.api_services, name="api_services"),
    path("api/incidents/", views.api_incidents, name="api_incidents"),
    path("api/incidents/<int:pk>/", views.api_incident_detail, name="api_incident_detail"),
]
