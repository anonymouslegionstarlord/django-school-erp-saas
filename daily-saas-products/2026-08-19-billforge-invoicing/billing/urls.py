from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/clients/", views.clients, name="clients"),
    path("app/invoices/", views.invoices, name="invoices"),
    path("app/invoices/new/", views.create_invoice, name="create_invoice"),
    path("app/invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("app/invoices/<int:pk>/items/", views.add_item, name="add_item"),
    path("app/invoices/<int:pk>/payments/", views.add_payment, name="add_payment"),
    path("app/invoices/<int:pk>/status/", views.update_status, name="update_status"),
    path("api/v1/summary/", views.api_summary, name="api_summary"),
    path("api/v1/invoices/", views.api_invoices, name="api_invoices"),
    path("api/v1/clients/", views.api_clients, name="api_clients"),
]
