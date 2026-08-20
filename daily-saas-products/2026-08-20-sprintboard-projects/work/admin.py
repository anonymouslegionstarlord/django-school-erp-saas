from django.contrib import admin

from .models import Comment, Membership, Organization, Project, Task

admin.site.register([Organization, Membership, Project, Task, Comment])
