from django.contrib import admin

from .models import (
    ActionItem,
    Incident,
    IncidentResponder,
    IncidentUpdate,
    Membership,
    Organization,
    Service,
)

admin.site.register(
    [
        Organization,
        Membership,
        Service,
        Incident,
        IncidentResponder,
        IncidentUpdate,
        ActionItem,
    ]
)
