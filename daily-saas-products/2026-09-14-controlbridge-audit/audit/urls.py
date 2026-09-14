from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/findings/", views.finding_list, name="finding_list"),
    path("app/findings/new/", views.finding_create, name="finding_create"),
    path("app/findings/<int:pk>/", views.finding_detail, name="finding_detail"),
    path("app/findings/<int:pk>/transition/", views.transition, name="transition"),
    path("app/findings/<int:pk>/tasks/", views.task_create, name="task_create"),
    path("app/tasks/<int:pk>/", views.task_update, name="task_update"),
    path("app/control_areas/", views.control_area_list, name="control_area_list"),
    path("track/<str:code>/", views.public_tracking, name="public_tracking"),
    path("api/findings/", views.api_findings, name="api_findings"),
    path("api/findings/<int:pk>/transition/", views.api_transition, name="api_transition"),
]
