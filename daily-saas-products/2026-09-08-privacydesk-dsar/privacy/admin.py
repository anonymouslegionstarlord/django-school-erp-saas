from django.contrib import admin

from .models import DataSubject, Membership, Organization, PrivacyRequest, RequestEvent, RequestTask

admin.site.register([Organization, Membership, DataSubject, PrivacyRequest, RequestTask, RequestEvent])
