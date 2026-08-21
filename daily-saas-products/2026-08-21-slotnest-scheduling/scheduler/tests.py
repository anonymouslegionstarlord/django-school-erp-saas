from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import AppointmentForm
from .models import Appointment, Customer, Membership, Organization, Service


class SlotNestTests(TestCase):
    def setUp(self):
        self.alpha = Organization.objects.create(name="Alpha Studio", slug="alpha")
        self.beta = Organization.objects.create(name="Beta Studio", slug="beta")
        self.owner = User.objects.create_user("alpha_owner", password="ValidPass123!")
        self.outsider = User.objects.create_user("beta_owner", password="ValidPass123!")
        Membership.objects.create(user=self.owner, organization=self.alpha, role="owner")
        Membership.objects.create(user=self.outsider, organization=self.beta, role="owner")
        self.service = Service.objects.create(
            organization=self.alpha, name="Consultation", duration_minutes=60, price="1500.00"
        )
        self.foreign_service = Service.objects.create(
            organization=self.beta, name="Foreign service", duration_minutes=30, price="900.00"
        )
        self.customer = Customer.objects.create(
            organization=self.alpha, name="Asha", email="asha@example.com"
        )
        self.foreign_customer = Customer.objects.create(
            organization=self.beta, name="Bea", email="bea@example.com"
        )
        self.starts = (timezone.now() + timedelta(days=1)).replace(second=0, microsecond=0)
        self.appointment = Appointment.objects.create(
            organization=self.alpha,
            customer=self.customer,
            service=self.service,
            staff=self.owner,
            starts_at=self.starts,
        )
        self.foreign_appointment = Appointment.objects.create(
            organization=self.beta,
            customer=self.foreign_customer,
            service=self.foreign_service,
            staff=self.outsider,
            starts_at=self.starts,
        )
        self.client.force_login(self.owner)

    def test_dashboard_only_contains_current_tenant(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Asha")
        self.assertNotContains(response, "Bea")

    def test_schedule_only_contains_current_tenant(self):
        response = self.client.get(reverse("schedule"), {"date": self.starts.date()})
        self.assertContains(response, "Consultation")
        self.assertNotContains(response, "Foreign service")

    def test_foreign_appointment_detail_is_not_found(self):
        response = self.client.get(
            reverse("appointment_detail", args=[self.foreign_appointment.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_service_is_created_inside_workspace(self):
        self.client.post(
            reverse("services"),
            {"name": "Review", "duration_minutes": 45, "price": "800", "color": "#112233"},
        )
        self.assertTrue(Service.objects.filter(organization=self.alpha, name="Review").exists())

    def test_customer_is_created_inside_workspace(self):
        self.client.post(
            reverse("customers"),
            {"name": "Cara", "email": "cara@example.com", "phone": "", "notes": ""},
        )
        self.assertTrue(
            Customer.objects.filter(organization=self.alpha, email="cara@example.com").exists()
        )

    def test_appointment_form_hides_foreign_records(self):
        form = AppointmentForm(organization=self.alpha)
        self.assertNotIn(self.foreign_customer, form.fields["customer"].queryset)
        self.assertNotIn(self.foreign_service, form.fields["service"].queryset)
        self.assertNotIn(self.outsider, form.fields["staff"].queryset)

    def test_duplicate_staff_start_is_rejected(self):
        form = AppointmentForm(
            {
                "customer": self.customer.pk,
                "service": self.service.pk,
                "staff": self.owner.pk,
                "starts_at": timezone.localtime(self.starts).strftime("%Y-%m-%dT%H:%M"),
                "notes": "",
            },
            organization=self.alpha,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("already has a booking", form.non_field_errors()[0])

    def test_owner_can_update_status(self):
        self.client.post(
            reverse("update_status", args=[self.appointment.pk]),
            {"status": Appointment.Status.COMPLETED},
        )
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.COMPLETED)

    def test_foreign_status_update_is_not_found(self):
        response = self.client.post(
            reverse("update_status", args=[self.foreign_appointment.pk]),
            {"status": Appointment.Status.COMPLETED},
        )
        self.assertEqual(response.status_code, 404)

    def test_appointment_computed_values(self):
        self.assertEqual(self.appointment.ends_at, self.starts + timedelta(minutes=60))
        self.assertEqual(self.appointment.revenue, 0)
        self.appointment.status = Appointment.Status.COMPLETED
        self.assertEqual(self.appointment.revenue, self.service.price)

    def test_summary_api_is_tenant_scoped(self):
        response = self.client.get(reverse("api_summary"))
        self.assertEqual(response.json()["workspace"], "Alpha Studio")
        self.assertEqual(response.json()["customers"], 1)

    def test_appointments_api_is_tenant_scoped(self):
        payload = self.client.get(reverse("api_appointments")).json()["results"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["customer"], "Asha")

    def test_services_api_is_tenant_scoped(self):
        payload = self.client.get(reverse("api_services")).json()["results"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["name"], "Consultation")

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("login"))

    def test_signup_creates_owner_workspace(self):
        self.client.logout()
        response = self.client.post(
            reverse("signup"),
            {
                "username": "newowner",
                "email": "new@example.com",
                "business_name": "Alpha Studio",
                "password1": "FreshValidPass123!",
                "password2": "FreshValidPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        member = User.objects.get(username="newowner").schedule_membership
        self.assertEqual(member.role, Membership.Role.OWNER)
        self.assertEqual(member.organization.slug, "alpha-studio")
