from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/reports/", views.report_list, name="report_list"),
    path("app/reports/new/", views.report_create, name="report_create"),
    path("app/reports/<int:pk>/", views.report_detail, name="report_detail"),
    path("app/reports/<int:pk>/edit/", views.report_edit, name="report_edit"),
    path("app/reports/<int:pk>/items/", views.item_add, name="item_add"),
    path(
        "app/reports/<int:pk>/items/<int:item_pk>/delete/",
        views.item_delete,
        name="item_delete",
    ),
    path("app/reports/<int:pk>/submit/", views.report_submit, name="report_submit"),
    path("app/reports/<int:pk>/decide/", views.report_decide, name="report_decide"),
    path(
        "app/reports/<int:pk>/reimburse/",
        views.report_reimburse,
        name="report_reimburse",
    ),
    path("app/reports/<int:pk>/comments/", views.comment_add, name="comment_add"),
    path("app/policy/", views.policy_settings, name="policy_settings"),
    path("api/summary/", views.api_summary, name="api_summary"),
    path("api/reports/", views.api_reports, name="api_reports"),
    path("api/reports/<int:pk>/", views.api_report_detail, name="api_report_detail"),
    path("api/policy/", views.api_policy, name="api_policy"),
]
