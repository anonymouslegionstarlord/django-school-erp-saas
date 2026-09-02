from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("claims/", views.claim_list, name="claim_list"),
    path("claims/new/", views.claim_create, name="claim_create"),
    path("claims/<int:pk>/", views.claim_detail, name="claim_detail"),
    path("claims/<int:pk>/transition/", views.claim_transition, name="claim_transition"),
    path("claims/<int:pk>/inspect/", views.claim_inspect, name="claim_inspect"),
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/products/new/", views.product_create, name="product_create"),
    path("catalog/items/new/", views.item_create, name="item_create"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/new/", views.customer_create, name="customer_create"),
    path("team/", views.team_list, name="team_list"),
    path("team/new/", views.team_create, name="team_create"),
    path(
        "track/<slug:organization_slug>/<str:tracking_code>/",
        views.public_tracking,
        name="public_tracking",
    ),
    path("api/v1/summary/", views.api_summary, name="api_summary"),
    path("api/v1/claims/", views.api_claims, name="api_claims"),
    path("api/v1/catalog/", views.api_catalog, name="api_catalog"),
    path("api/v1/claims/<int:pk>/transition/", views.api_transition, name="api_transition"),
]
