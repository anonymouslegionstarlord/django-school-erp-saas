from django.contrib import admin

from .models import (
    Activity,
    Application,
    Candidate,
    Interview,
    JobOpening,
    Membership,
    Organization,
)

admin.site.register(
    [Organization, Membership, JobOpening, Candidate, Application, Interview, Activity]
)
