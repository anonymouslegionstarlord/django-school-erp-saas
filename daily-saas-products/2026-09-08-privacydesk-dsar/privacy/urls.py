from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/requests/", views.request_list, name="request_list"),
    path("app/requests/new/", views.request_create, name="request_create"),
    path("app/requests/<int:pk>/", views.request_detail, name="request_detail"),
    path("app/requests/<int:pk>/transition/", views.transition, name="transition"),
    path("app/requests/<int:pk>/tasks/", views.task_create, name="task_create"),
    path("app/tasks/<int:pk>/", views.task_update, name="task_update"),
    path("app/subjects/", views.subject_list, name="subject_list"),
    path("track/<str:code>/", views.public_tracking, name="public_tracking"),
    path("api/requests/", views.api_requests, name="api_requests"),
    path("api/requests/<int:pk>/transition/", views.api_transition, name="api_transition"),
]
