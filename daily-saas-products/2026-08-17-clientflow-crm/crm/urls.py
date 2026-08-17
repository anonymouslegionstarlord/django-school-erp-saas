from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/contacts/", views.contacts, name="contacts"),
    path("app/deals/", views.deals, name="deals"),
    path("app/deals/<int:pk>/stage/", views.update_stage, name="update_stage"),
    path("app/deals/<int:pk>/activity/", views.add_activity, name="add_activity"),
    path("api/v1/summary/", views.api_summary, name="api_summary"),
    path("api/v1/contacts/", views.api_contacts, name="api_contacts"),
    path("api/v1/deals/", views.api_deals, name="api_deals"),
]
