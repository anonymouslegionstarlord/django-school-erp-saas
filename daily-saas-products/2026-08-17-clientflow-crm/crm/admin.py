from django.contrib import admin

from .models import Activity, Contact, Deal, Membership, Organization

admin.site.register([Organization, Membership, Contact, Deal, Activity])
