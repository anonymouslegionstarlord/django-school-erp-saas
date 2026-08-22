from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/products/", views.products, name="products"),
    path("app/suppliers/", views.suppliers, name="suppliers"),
    path("app/movements/", views.movements, name="movements"),
    path("app/purchase-orders/", views.purchase_orders, name="purchase_orders"),
    path(
        "app/purchase-orders/<int:pk>/",
        views.purchase_order_detail,
        name="purchase_order_detail",
    ),
    path(
        "app/purchase-orders/<int:pk>/receive/",
        views.receive_purchase_order,
        name="receive_purchase_order",
    ),
    path("api/summary/", views.api_summary, name="api_summary"),
    path("api/products/", views.api_products, name="api_products"),
    path("api/movements/", views.api_movements, name="api_movements"),
]
