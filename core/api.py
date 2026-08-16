from rest_framework import permissions, viewsets

from .middleware import resolve_active_school
from .models import Course, Invoice, Membership, Student, Teacher
from .serializers import CourseSerializer, InvoiceSerializer, StudentSerializer, TeacherSerializer


class SchoolMemberPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user.is_authenticated and not getattr(request, "school", None):
            resolve_active_school(request)
        if not request.user.is_authenticated or not request.school:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        allowed_roles = getattr(view, "write_roles", {Membership.Role.OWNER, Membership.Role.ADMIN})
        return bool(request.membership and request.membership.role in allowed_roles)


class TenantModelViewSet(viewsets.ModelViewSet):
    permission_classes = [SchoolMemberPermission]

    def get_queryset(self):
        if not getattr(self.request, "school", None):
            return self.queryset.none()
        return self.queryset.filter(school=self.request.school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.school)


class StudentViewSet(TenantModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer


class TeacherViewSet(TenantModelViewSet):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer


class CourseViewSet(TenantModelViewSet):
    queryset = Course.objects.select_related("teacher")
    serializer_class = CourseSerializer


class InvoiceViewSet(TenantModelViewSet):
    queryset = Invoice.objects.select_related("student")
    serializer_class = InvoiceSerializer
    write_roles = {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.ACCOUNTANT}
