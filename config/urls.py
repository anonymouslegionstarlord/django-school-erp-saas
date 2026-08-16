from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from core import api

router = DefaultRouter()
router.register("students", api.StudentViewSet, basename="api-student")
router.register("teachers", api.TeacherViewSet, basename="api-teacher")
router.register("courses", api.CourseViewSet, basename="api-course")
router.register("invoices", api.InvoiceViewSet, basename="api-invoice")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("api/", include(router.urls)),
    path("", include("core.urls")),
]
