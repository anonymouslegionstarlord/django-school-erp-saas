from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/vendors/", views.vendor_list, name="vendor_list"),
    path("app/vendors/new/", views.vendor_create, name="vendor_create"),
    path("app/vendors/<int:pk>/", views.vendor_detail, name="vendor_detail"),
    path("app/vendors/<int:pk>/edit/", views.vendor_edit, name="vendor_edit"),
    path("app/assessments/", views.assessment_list, name="assessment_list"),
    path("app/assessments/new/", views.assessment_create, name="assessment_create"),
    path("app/assessments/<int:pk>/", views.assessment_detail, name="assessment_detail"),
    path(
        "app/assessments/<int:assessment_pk>/controls/<int:pk>/",
        views.control_update,
        name="control_update",
    ),
    path(
        "app/assessments/<int:pk>/transition/",
        views.assessment_transition,
        name="assessment_transition",
    ),
    path(
        "app/assessments/<int:assessment_pk>/findings/",
        views.finding_add,
        name="finding_add",
    ),
    path("app/findings/<int:pk>/", views.finding_update, name="finding_update"),
    path("api/summary/", views.api_summary, name="api_summary"),
    path("api/vendors/", views.api_vendors, name="api_vendors"),
    path("api/assessments/", views.api_assessments, name="api_assessments"),
    path("api/findings/", views.api_findings, name="api_findings"),
]
