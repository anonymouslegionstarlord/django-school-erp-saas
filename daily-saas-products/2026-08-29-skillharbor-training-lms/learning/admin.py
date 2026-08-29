from django.contrib import admin

from .models import Activity, Course, Enrollment, LessonProgress, Membership, Module, Organization

admin.site.register(
    [Organization, Membership, Course, Module, Enrollment, LessonProgress, Activity]
)
