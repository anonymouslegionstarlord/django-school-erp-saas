from django.contrib import admin

from .models import LeaveRequest, LeaveType, Membership, Organization

admin.site.register([Organization, Membership, LeaveType, LeaveRequest])
