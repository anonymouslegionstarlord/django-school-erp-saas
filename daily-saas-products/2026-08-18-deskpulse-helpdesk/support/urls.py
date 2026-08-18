from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/customers/", views.customers, name="customers"),
    path("app/tickets/", views.tickets, name="tickets"),
    path("app/tickets/new/", views.create_ticket, name="create_ticket"),
    path("app/tickets/<int:pk>/", views.ticket_detail, name="ticket_detail"),
    path("app/tickets/<int:pk>/update/", views.update_ticket, name="update_ticket"),
    path("api/v1/summary/", views.api_summary, name="api_summary"),
    path("api/v1/tickets/", views.api_tickets, name="api_tickets"),
    path("api/v1/customers/", views.api_customers, name="api_customers"),
]
