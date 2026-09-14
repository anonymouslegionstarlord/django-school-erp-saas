from django.contrib import admin

from .models import AuditFinding, ControlArea, FindingEvent, Membership, Organization, RemediationTask

admin.site.register([Organization, Membership, ControlArea, AuditFinding, RemediationTask, FindingEvent])
