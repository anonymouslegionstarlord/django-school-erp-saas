from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Comment, Membership, Organization, Project, Task


class WorkspaceTests(TestCase):
    def setUp(self):
        self.a = Organization.objects.create(name="Alpha", slug="alpha")
        self.b = Organization.objects.create(name="Beta", slug="beta")
        self.ua = User.objects.create_user("alpha", password="StrongPass123!")
        self.ub = User.objects.create_user("beta", password="StrongPass123!")
        Membership.objects.create(user=self.ua, organization=self.a, role="owner")
        Membership.objects.create(user=self.ub, organization=self.b, role="owner")
        self.pa = Project.objects.create(organization=self.a, name="Alpha Project", code="ALP")
        self.pb = Project.objects.create(organization=self.b, name="Secret Beta", code="BET")
        self.ta = Task.objects.create(
            organization=self.a, project=self.pa, title="Alpha Task", assignee=self.ua, due_date=timezone.localdate() + timedelta(days=2)
        )
        self.tb = Task.objects.create(organization=self.b, project=self.pb, title="Secret Task", assignee=self.ub)
        self.client.force_login(self.ua)

    def test_dashboard_tenant_scope(self):
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "Alpha Task")
        self.assertNotContains(r, "Secret Task")

    def test_board_tenant_scope(self):
        r = self.client.get(reverse("board"))
        self.assertContains(r, "Alpha Task")
        self.assertNotContains(r, "Secret Task")

    def test_foreign_detail_404(self):
        self.assertEqual(self.client.get(reverse("task_detail", args=[self.tb.pk])).status_code, 404)

    def test_create_project_assigns_tenant(self):
        self.client.post(reverse("projects"), {"name": "New", "code": "NEW", "color": "#112233"})
        self.assertTrue(Project.objects.filter(organization=self.a, code="NEW").exists())

    def test_task_form_rejects_foreign_project(self):
        r = self.client.post(
            reverse("create_task"),
            {"project": self.pb.pk, "title": "Intrusion", "status": "todo", "priority": "high", "assignee": self.ua.pk},
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Task.objects.filter(title="Intrusion").exists())

    def test_task_form_rejects_foreign_assignee(self):
        r = self.client.post(
            reverse("create_task"),
            {"project": self.pa.pk, "title": "Intrusion", "status": "todo", "priority": "high", "assignee": self.ub.pk},
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Task.objects.filter(title="Intrusion").exists())

    def test_comment_records_tenant_author(self):
        self.client.post(reverse("task_detail", args=[self.ta.pk]), {"body": "Progress update"})
        c = Comment.objects.get(task=self.ta)
        self.assertEqual(c.organization, self.a)
        self.assertEqual(c.author, self.ua)

    def test_foreign_update_404(self):
        self.assertEqual(self.client.post(reverse("update_task", args=[self.tb.pk]), {"status": "done"}).status_code, 404)

    def test_status_update(self):
        self.client.post(reverse("update_task", args=[self.ta.pk]), {"status": "done", "priority": "urgent"})
        self.ta.refresh_from_db()
        self.assertEqual(self.ta.status, "done")
        self.assertEqual(self.ta.priority, "urgent")

    def test_api_tenant_scope(self):
        p = self.client.get(reverse("api_tasks")).json()
        self.assertEqual(len(p["results"]), 1)
        self.assertEqual(p["results"][0]["title"], "Alpha Task")

    def test_api_summary(self):
        p = self.client.get(reverse("api_summary")).json()
        self.assertEqual(p["projects"], 1)
        self.assertEqual(p["active_tasks"], 1)

    def test_anonymous_api_redirect(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("api_projects")).status_code, 302)

    def test_overdue_logic(self):
        self.ta.due_date = timezone.localdate() - timedelta(days=1)
        self.ta.save()
        self.assertTrue(self.ta.is_overdue)
        self.ta.status = "done"
        self.ta.save()
        self.assertFalse(self.ta.is_overdue)


class SignupTests(TestCase):
    def test_signup_creates_owner(self):
        r = self.client.post(
            reverse("signup"),
            {
                "username": "founder",
                "email": "f@example.com",
                "workspace_name": "Orbit Team",
                "password1": "VeryStrongPass123!",
                "password2": "VeryStrongPass123!",
            },
        )
        self.assertRedirects(r, reverse("dashboard"))
        self.assertEqual(User.objects.get(username="founder").work_membership.role, "owner")

    def test_slug_collision(self):
        Organization.objects.create(name="Orbit Team", slug="orbit-team")
        self.client.post(
            reverse("signup"),
            {
                "username": "founder",
                "email": "f@example.com",
                "workspace_name": "Orbit Team",
                "password1": "VeryStrongPass123!",
                "password2": "VeryStrongPass123!",
            },
        )
        self.assertEqual(User.objects.get(username="founder").work_membership.organization.slug, "orbit-team-2")
