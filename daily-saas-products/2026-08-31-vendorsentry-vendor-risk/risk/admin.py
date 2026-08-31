from django.contrib import admin

from .models import (
    Activity,
    Assessment,
    AssessmentControl,
    Finding,
    Membership,
    Organization,
    Vendor,
)

admin.site.register(
    [
        Organization,
        Membership,
        Vendor,
        Assessment,
        AssessmentControl,
        Finding,
        Activity,
    ]
)
