from django.contrib import admin

from .models import Activity, Contract, Counterparty, Membership, Obligation, Organization

admin.site.register([Organization, Membership, Counterparty, Contract, Obligation, Activity])
