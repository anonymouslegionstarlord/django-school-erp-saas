from django.contrib import admin

from .models import Client, Invoice, LineItem, Membership, Organization, Payment

admin.site.register([Organization, Membership, Client, Invoice, LineItem, Payment])
