from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/jobs/", views.job_list, name="job_list"),
    path("app/jobs/new/", views.job_create, name="job_create"),
    path("app/jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("app/candidates/", views.candidate_list, name="candidate_list"),
    path("app/pipeline/", views.pipeline, name="pipeline"),
    path("app/applications/new/", views.application_create, name="application_create"),
    path("app/applications/<int:pk>/", views.application_detail, name="application_detail"),
    path(
        "app/applications/<int:pk>/update/",
        views.application_update,
        name="application_update",
    ),
    path("app/applications/<int:pk>/interviews/", views.interview_add, name="interview_add"),
    path("app/applications/<int:pk>/activity/", views.activity_add, name="activity_add"),
    path("app/interviews/", views.interview_list, name="interview_list"),
    path(
        "app/interviews/<int:pk>/feedback/",
        views.interview_feedback,
        name="interview_feedback",
    ),
    path("api/summary/", views.api_summary, name="api_summary"),
    path("api/jobs/", views.api_jobs, name="api_jobs"),
    path("api/applications/", views.api_applications, name="api_applications"),
    path("api/interviews/", views.api_interviews, name="api_interviews"),
]
