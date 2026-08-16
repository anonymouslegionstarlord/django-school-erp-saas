from django.contrib import admin

from .models import Attendance, Course, Enrollment, Invoice, Membership, Payment, School, Student, Teacher


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "plan", "is_active", "created_at")
    search_fields = ("name", "slug", "email")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "role", "is_active")
    list_filter = ("role", "is_active")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("admission_number", "full_name", "school", "class_name", "section", "is_active")
    list_filter = ("school", "class_name", "is_active")
    search_fields = ("admission_number", "first_name", "last_name", "guardian_name")


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "full_name", "school", "subject", "is_active")
    list_filter = ("school", "subject", "is_active")


admin.site.register(Course)
admin.site.register(Enrollment)
admin.site.register(Attendance)
admin.site.register(Invoice)
admin.site.register(Payment)
