from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/work-orders/", views.work_orders, name="work_orders"),
    path("app/work-orders/new/", views.create_work_order, name="create_work_order"),
    path("app/work-orders/<int:pk>/", views.work_order_detail, name="work_order_detail"),
    path("app/assets/", views.assets, name="assets"),
    path("app/sites/", views.sites, name="sites"),
    path("api/summary/", views.api_summary, name="api_summary"),
    path("api/work-orders/", views.api_work_orders, name="api_work_orders"),
    path("api/assets/", views.api_assets, name="api_assets"),
]
