from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/courses/", views.course_list, name="course_list"),
    path("app/courses/new/", views.course_create, name="course_create"),
    path("app/courses/<int:pk>/", views.course_detail, name="course_detail"),
    path("app/courses/<int:pk>/edit/", views.course_edit, name="course_edit"),
    path("app/courses/<int:pk>/publish/", views.course_publish, name="course_publish"),
    path("app/courses/<int:course_pk>/modules/new/", views.module_create, name="module_create"),
    path(
        "app/courses/<int:course_pk>/modules/<int:pk>/edit/",
        views.module_edit,
        name="module_edit",
    ),
    path("app/enrollments/", views.enrollment_list, name="enrollment_list"),
    path("app/enrollments/new/", views.enrollment_create, name="enrollment_create"),
    path("app/enrollments/<int:pk>/", views.enrollment_detail, name="enrollment_detail"),
    path(
        "app/enrollments/<int:enrollment_pk>/modules/<int:pk>/",
        views.progress_update,
        name="progress_update",
    ),
    path("app/enrollments/<int:pk>/grade/", views.enrollment_grade, name="enrollment_grade"),
    path(
        "app/enrollments/<int:pk>/comments/",
        views.enrollment_comment,
        name="enrollment_comment",
    ),
    path("api/summary/", views.api_summary, name="api_summary"),
    path("api/courses/", views.api_courses, name="api_courses"),
    path("api/enrollments/", views.api_enrollments, name="api_enrollments"),
    path("api/enrollments/<int:pk>/", views.api_enrollment_detail, name="api_enrollment_detail"),
]
