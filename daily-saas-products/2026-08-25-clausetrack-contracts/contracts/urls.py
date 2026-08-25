from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/contracts/", views.contract_list, name="contract_list"),
    path("app/contracts/new/", views.contract_create, name="contract_create"),
    path("app/contracts/<int:pk>/", views.contract_detail, name="contract_detail"),
    path("app/contracts/<int:pk>/update/", views.contract_update, name="contract_update"),
    path("app/contracts/<int:pk>/obligations/", views.obligation_add, name="obligation_add"),
    path("app/contracts/<int:pk>/activity/", views.activity_add, name="activity_add"),
    path("app/obligations/", views.obligation_list, name="obligation_list"),
    path(
        "app/obligations/<int:pk>/complete/", views.obligation_complete, name="obligation_complete"
    ),
    path("app/counterparties/", views.counterparties, name="counterparties"),
    path("api/summary/", views.api_summary, name="api_summary"),
    path("api/contracts/", views.api_contracts, name="api_contracts"),
    path("api/obligations/", views.api_obligations, name="api_obligations"),
]
