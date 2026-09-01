from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("shipments/", views.shipment_list, name="shipment_list"),
    path("shipments/new/", views.shipment_create, name="shipment_create"),
    path("shipments/<int:pk>/", views.shipment_detail, name="shipment_detail"),
    path("shipments/<int:pk>/assign/", views.shipment_assign, name="shipment_assign"),
    path("shipments/<int:pk>/transition/", views.shipment_transition, name="shipment_transition"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/new/", views.customer_create, name="customer_create"),
    path("fleet/", views.fleet_list, name="fleet_list"),
    path("fleet/vehicles/new/", views.vehicle_create, name="vehicle_create"),
    path("fleet/drivers/new/", views.driver_create, name="driver_create"),
    path(
        "track/<slug:organization_slug>/<str:tracking_code>/",
        views.public_tracking,
        name="public_tracking",
    ),
    path("api/v1/summary/", views.api_summary, name="api_summary"),
    path("api/v1/shipments/", views.api_shipments, name="api_shipments"),
    path("api/v1/fleet/", views.api_fleet, name="api_fleet"),
    path("api/v1/shipments/<int:pk>/transition/", views.api_transition, name="api_transition"),
]
