from django.contrib import admin

from .models import Asset, Membership, Organization, Site, WorkLog, WorkOrder

admin.site.register([Organization, Membership, Site, Asset, WorkOrder, WorkLog])
