from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup/", views.signup, name="signup"),
    path("app/", views.dashboard, name="dashboard"),
    path("app/requests/", views.requests_list, name="requests"),
    path("app/requests/new/", views.create_request, name="create_request"),
    path("app/requests/<int:pk>/review/", views.review_request, name="review_request"),
    path("app/requests/<int:pk>/cancel/", views.cancel_request, name="cancel_request"),
    path("app/calendar/", views.team_calendar, name="calendar"),
    path("app/team/", views.team, name="team"),
    path("api/summary/", views.api_summary, name="api_summary"),
    path("api/requests/", views.api_requests, name="api_requests"),
    path("api/calendar/", views.api_calendar, name="api_calendar"),
]
