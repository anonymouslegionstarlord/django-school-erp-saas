from django.contrib import admin
from .models import Appointment, Customer, Membership, Organization, Service

admin.site.register([Organization, Membership, Service, Customer, Appointment])
