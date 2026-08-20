from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="work_membership")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.MEMBER)


class Project(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=140)
    code = models.CharField(max_length=12)
    description = models.TextField(max_length=1000, blank=True)
    color = models.CharField(max_length=7, default="#6C5CE7")
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="unique_project_code_per_org")]

    def __str__(self):
        return self.name


class Task(models.Model):
    class Status(models.TextChoices):
        BACKLOG = "backlog", "Backlog"
        TODO = "todo", "To do"
        DOING = "doing", "In progress"
        REVIEW = "review", "Review"
        DONE = "done", "Done"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="tasks")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=180)
    description = models.TextField(max_length=3000, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.BACKLOG)
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.MEDIUM)
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_tasks")
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    @property
    def is_overdue(self):
        return bool(self.due_date and self.status != self.Status.DONE and self.due_date < timezone.localdate())

    def __str__(self):
        return self.title


class Comment(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="comments")
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.PROTECT)
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
