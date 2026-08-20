from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/projects/", views.projects, name="projects"),
    path("app/board/", views.board, name="board"),
    path("app/tasks/new/", views.create_task, name="create_task"),
    path("app/tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("app/tasks/<int:pk>/update/", views.update_task, name="update_task"),
    path("api/v1/summary/", views.api_summary, name="api_summary"),
    path("api/v1/tasks/", views.api_tasks, name="api_tasks"),
    path("api/v1/projects/", views.api_projects, name="api_projects"),
]
