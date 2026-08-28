from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/products/", views.product_list, name="product_list"),
    path("app/products/new/", views.product_create, name="product_create"),
    path("app/products/<int:pk>/", views.product_detail, name="product_detail"),
    path("app/products/<int:pk>/suites/", views.suite_add, name="suite_add"),
    path("app/cases/", views.case_list, name="case_list"),
    path("app/cases/new/", views.case_create, name="case_create"),
    path("app/cases/<int:pk>/", views.case_detail, name="case_detail"),
    path("app/cases/<int:pk>/edit/", views.case_edit, name="case_edit"),
    path("app/runs/", views.run_list, name="run_list"),
    path("app/runs/new/", views.run_create, name="run_create"),
    path("app/runs/<int:pk>/", views.run_detail, name="run_detail"),
    path("app/runs/<int:pk>/add-cases/", views.run_add_cases, name="run_add_cases"),
    path("app/runs/<int:pk>/start/", views.run_start, name="run_start"),
    path("app/runs/<int:pk>/complete/", views.run_complete, name="run_complete"),
    path("app/runs/<int:pk>/comments/", views.run_comment, name="run_comment"),
    path(
        "app/runs/<int:run_pk>/executions/<int:pk>/",
        views.execution_update,
        name="execution_update",
    ),
    path("api/summary/", views.api_summary, name="api_summary"),
    path("api/products/", views.api_products, name="api_products"),
    path("api/cases/", views.api_cases, name="api_cases"),
    path("api/runs/", views.api_runs, name="api_runs"),
    path("api/runs/<int:pk>/", views.api_run_detail, name="api_run_detail"),
]
