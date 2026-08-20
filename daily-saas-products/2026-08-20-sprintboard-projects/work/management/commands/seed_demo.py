from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from work.models import Comment, Membership, Organization, Project, Task


class Command(BaseCommand):
    help = "Create or reset a safe local SprintBoard demo workspace"

    @transaction.atomic
    def handle(self, *args, **options):
        user, _ = User.objects.get_or_create(username="demo_lead", defaults={"email": "demo@sprintboard.local", "first_name": "Demo"})
        user.set_password("DemoPass123!")
        user.save()
        org, _ = Organization.objects.get_or_create(slug="northstar-team", defaults={"name": "Northstar Team"})
        Membership.objects.update_or_create(user=user, defaults={"organization": org, "role": Membership.Role.OWNER})
        Comment.objects.filter(organization=org).delete()
        Task.objects.filter(organization=org).delete()
        Project.objects.filter(organization=org).delete()
        web = Project.objects.create(
            organization=org, name="Website Launch", code="WEB", description="Launch the refreshed marketing site.", color="#6C5CE7"
        )
        mobile = Project.objects.create(
            organization=org, name="Mobile Experience", code="APP", description="Improve activation and retention.", color="#F08068"
        )
        today = timezone.localdate()
        tasks = [
            Task.objects.create(
                organization=org,
                project=web,
                title="Finalize responsive layouts",
                description="Review tablet and mobile breakpoints.",
                status="todo",
                priority="high",
                assignee=user,
                due_date=today,
            ),
            Task.objects.create(
                organization=org,
                project=web,
                title="Connect payment API",
                description="Implement checkout and webhook verification.",
                status="doing",
                priority="urgent",
                assignee=user,
                due_date=today + timedelta(days=2),
            ),
            Task.objects.create(
                organization=org,
                project=web,
                title="QA checkout flow",
                description="Cover successful, failed, and abandoned payments.",
                status="review",
                priority="high",
                assignee=user,
                due_date=today + timedelta(days=3),
            ),
            Task.objects.create(
                organization=org,
                project=mobile,
                title="Instrument onboarding events",
                description="Track the activation funnel.",
                status="backlog",
                priority="medium",
                due_date=today + timedelta(days=8),
            ),
            Task.objects.create(
                organization=org,
                project=mobile,
                title="Ship empty-state illustrations",
                status="done",
                priority="low",
                assignee=user,
                due_date=today - timedelta(days=1),
            ),
        ]
        Comment.objects.create(
            organization=org, task=tasks[1], author=user, body="Sandbox payment flow is working; webhook signature verification is next."
        )
        self.stdout.write(self.style.SUCCESS("Demo ready: demo_lead / DemoPass123!"))
