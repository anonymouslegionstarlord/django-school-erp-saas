from django.contrib import admin

from .models import Customer, Membership, Organization, Reply, Ticket

admin.site.register([Organization, Membership, Customer, Ticket, Reply])
