from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Invoice, Membership, Payment, School, Student


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.school_a = School.objects.create(name="Alpha School", slug="alpha-school")
        self.school_b = School.objects.create(name="Beta School", slug="beta-school")
        self.user_a = User.objects.create_user("alpha-owner", password="TestPass123!")
        self.user_b = User.objects.create_user("beta-owner", password="TestPass123!")
        Membership.objects.create(user=self.user_a, school=self.school_a, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.user_b, school=self.school_b, role=Membership.Role.OWNER)
        self.student_a = Student.objects.create(
            school=self.school_a,
            admission_number="A-001",
            first_name="Alpha",
            guardian_name="Parent A",
            guardian_phone="1111111111",
            class_name="8",
        )
        self.student_b = Student.objects.create(
            school=self.school_b,
            admission_number="B-001",
            first_name="Beta",
            guardian_name="Parent B",
            guardian_phone="2222222222",
            class_name="8",
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_html_directory_never_leaks_another_school(self):
        self.client.login(username="alpha-owner", password="TestPass123!")
        response = self.client.get(reverse("students"))
        self.assertContains(response, "Alpha")
        self.assertNotContains(response, "Beta")

    def test_html_create_forces_active_school(self):
        self.client.login(username="alpha-owner", password="TestPass123!")
        self.client.post(
            reverse("students"),
            {
                "admission_number": "A-002",
                "first_name": "New",
                "last_name": "Student",
                "email": "",
                "guardian_name": "Parent",
                "guardian_phone": "9999999999",
                "class_name": "9",
                "section": "A",
                "enrolled_on": timezone.localdate(),
                "is_active": True,
            },
        )
        self.assertTrue(Student.objects.filter(school=self.school_a, admission_number="A-002").exists())
        self.assertFalse(Student.objects.filter(school=self.school_b, admission_number="A-002").exists())

    def test_api_queryset_is_tenant_scoped(self):
        client = APIClient()
        client.force_authenticate(self.user_a)
        response = client.get("/api/students/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["admission_number"], "A-001")

    def test_api_rejects_cross_tenant_detail(self):
        client = APIClient()
        client.force_authenticate(self.user_a)
        response = client.get(f"/api/students/{self.student_b.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_management_pages_render_for_school_owner(self):
        self.client.login(username="alpha-owner", password="TestPass123!")
        for url_name in ("dashboard", "teachers", "courses", "attendance", "invoices"):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)


class SignUpAndFinanceTests(TestCase):
    def test_signup_creates_owner_and_school(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "new-owner",
                "first_name": "New",
                "last_name": "Owner",
                "email": "owner@example.com",
                "school_name": "New Horizon School",
                "password1": "StrongPass987!",
                "password2": "StrongPass987!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        membership = Membership.objects.select_related("school").get(user__username="new-owner")
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(membership.school.name, "New Horizon School")

    def test_payment_updates_invoice_status(self):
        school = School.objects.create(name="Finance School", slug="finance-school")
        student = Student.objects.create(
            school=school,
            admission_number="F-001",
            first_name="Fee",
            guardian_name="Parent",
            guardian_phone="9999999999",
            class_name="5",
        )
        invoice = Invoice.objects.create(
            school=school,
            student=student,
            title="Tuition",
            amount=Decimal("1000.00"),
            due_date=timezone.localdate() + timedelta(days=5),
        )
        Payment.objects.create(invoice=invoice, amount=Decimal("400.00"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PARTIAL)
        Payment.objects.create(invoice=invoice, amount=Decimal("600.00"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.balance, Decimal("0.00"))


class HealthCheckTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
