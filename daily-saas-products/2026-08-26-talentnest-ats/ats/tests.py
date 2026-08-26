from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ApplicationForm, InterviewFeedbackForm, InterviewForm
from .models import (
    Activity,
    Application,
    Candidate,
    Interview,
    JobOpening,
    Membership,
    Organization,
)


class TalentNestTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Alpha Talent", slug="alpha")
        self.other_org = Organization.objects.create(name="Beta Talent", slug="beta")
        self.owner = User.objects.create_user("owner", password="TestPass123!")
        self.recruiter = User.objects.create_user("recruiter", password="TestPass123!")
        self.interviewer = User.objects.create_user("interviewer", password="TestPass123!")
        self.second_interviewer = User.objects.create_user(
            "second_interviewer", password="TestPass123!"
        )
        self.foreign_user = User.objects.create_user("foreign", password="TestPass123!")
        Membership.objects.create(
            user=self.owner, organization=self.org, role=Membership.Role.OWNER
        )
        Membership.objects.create(
            user=self.recruiter, organization=self.org, role=Membership.Role.RECRUITER
        )
        Membership.objects.create(
            user=self.interviewer, organization=self.org, role=Membership.Role.INTERVIEWER
        )
        Membership.objects.create(
            user=self.second_interviewer,
            organization=self.org,
            role=Membership.Role.INTERVIEWER,
        )
        Membership.objects.create(
            user=self.foreign_user,
            organization=self.other_org,
            role=Membership.Role.OWNER,
        )
        self.job = JobOpening.objects.create(
            organization=self.org,
            code="ENG-1",
            title="Python Engineer",
            department="Engineering",
            location="Remote",
            status=JobOpening.Status.OPEN,
            recruiter=self.recruiter,
            description="Build reliable services.",
        )
        self.foreign_job = JobOpening.objects.create(
            organization=self.other_org,
            code="SECRET-1",
            title="Secret Role",
            department="Strategy",
            location="Remote",
            status=JobOpening.Status.OPEN,
            recruiter=self.foreign_user,
            description="Private role.",
        )
        self.candidate = Candidate.objects.create(
            organization=self.org,
            name="Asha",
            email="asha@example.com",
            source=Candidate.Source.LINKEDIN,
            skills="Python, Django",
        )
        self.foreign_candidate = Candidate.objects.create(
            organization=self.other_org,
            name="Foreign Candidate",
            email="foreign@example.com",
        )
        self.application = Application.objects.create(
            organization=self.org,
            job=self.job,
            candidate=self.candidate,
            owner=self.recruiter,
            stage=Application.Stage.SCREENING,
            rating=4,
        )
        self.foreign_application = Application.objects.create(
            organization=self.other_org,
            job=self.foreign_job,
            candidate=self.foreign_candidate,
            owner=self.foreign_user,
        )
        self.starts = (timezone.now() + timedelta(days=2)).replace(second=0, microsecond=0)
        self.interview = Interview.objects.create(
            organization=self.org,
            application=self.application,
            interviewer=self.interviewer,
            scheduled_at=self.starts,
        )
        self.foreign_interview = Interview.objects.create(
            organization=self.other_org,
            application=self.foreign_application,
            interviewer=self.foreign_user,
            scheduled_at=self.starts,
        )

    def login(self, user=None):
        self.client.force_login(user or self.owner)

    def test_anonymous_dashboard_redirects(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_dashboard_is_tenant_scoped(self):
        self.login()
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Asha")
        self.assertNotContains(response, "Foreign Candidate")

    def test_job_list_searches_and_isolates(self):
        self.login()
        response = self.client.get(reverse("job_list"), {"q": "Python"})
        self.assertContains(response, "Python Engineer")
        self.assertNotContains(response, "Secret Role")

    def test_foreign_job_detail_is_not_found(self):
        self.login()
        self.assertEqual(
            self.client.get(reverse("job_detail", args=[self.foreign_job.pk])).status_code,
            404,
        )

    def test_recruiter_creates_job_in_workspace(self):
        self.login(self.recruiter)
        response = self.client.post(
            reverse("job_create"),
            {
                "code": "DES-2",
                "title": "Product Designer",
                "department": "Design",
                "location": "Delhi",
                "employment_type": JobOpening.EmploymentType.FULL_TIME,
                "status": JobOpening.Status.OPEN,
                "openings": 1,
                "recruiter": self.recruiter.pk,
                "description": "Design useful workflows.",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JobOpening.objects.filter(organization=self.org, code="DES-2").exists())

    def test_interviewer_cannot_create_job(self):
        self.login(self.interviewer)
        response = self.client.get(reverse("job_create"))
        self.assertRedirects(response, reverse("job_list"))

    def test_candidate_creation_is_scoped(self):
        self.login(self.recruiter)
        response = self.client.post(
            reverse("candidate_list"),
            {
                "name": "Rohan",
                "email": "rohan@example.com",
                "phone": "",
                "current_company": "Acme",
                "source": Candidate.Source.REFERRAL,
                "skills": "Figma",
            },
        )
        self.assertRedirects(response, reverse("candidate_list"))
        self.assertTrue(
            Candidate.objects.filter(organization=self.org, email="rohan@example.com").exists()
        )

    def test_interviewer_cannot_create_candidate(self):
        self.login(self.interviewer)
        response = self.client.post(
            reverse("candidate_list"),
            {
                "name": "No Access",
                "email": "no@example.com",
                "source": Candidate.Source.OTHER,
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_application_form_hides_foreign_relations(self):
        form = ApplicationForm(organization=self.org)
        self.assertNotIn(self.foreign_job, form.fields["job"].queryset)
        self.assertNotIn(self.foreign_candidate, form.fields["candidate"].queryset)
        self.assertNotIn(self.foreign_user, form.fields["owner"].queryset)

    def test_owner_creates_application_and_activity(self):
        candidate = Candidate.objects.create(
            organization=self.org, name="New Person", email="new@example.com"
        )
        self.login()
        response = self.client.post(
            reverse("application_create"),
            {
                "job": self.job.pk,
                "candidate": candidate.pk,
                "owner": self.recruiter.pk,
                "stage": Application.Stage.APPLIED,
                "rating": 3,
                "summary": "Promising profile",
            },
        )
        self.assertEqual(response.status_code, 302)
        application = Application.objects.get(candidate=candidate, job=self.job)
        self.assertEqual(application.organization, self.org)
        self.assertTrue(Activity.objects.filter(application=application).exists())

    def test_pipeline_is_tenant_scoped(self):
        self.login()
        response = self.client.get(reverse("pipeline"))
        self.assertContains(response, "Asha")
        self.assertNotContains(response, "Foreign Candidate")

    def test_foreign_application_detail_is_not_found(self):
        self.login()
        self.assertEqual(
            self.client.get(
                reverse("application_detail", args=[self.foreign_application.pk])
            ).status_code,
            404,
        )

    def test_application_detail_renders_interview_workflow(self):
        self.login()
        response = self.client.get(reverse("application_detail", args=[self.application.pk]))
        self.assertContains(response, "Video interview")
        self.assertContains(response, "Schedule an interview")

    def test_owner_updates_stage_and_records_activity(self):
        self.login()
        self.client.post(
            reverse("application_update", args=[self.application.pk]),
            {
                "stage": Application.Stage.OFFER,
                "owner": self.recruiter.pk,
                "rating": 5,
                "summary": "Approved",
            },
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.stage, Application.Stage.OFFER)
        self.assertTrue(
            Activity.objects.filter(
                application=self.application, message__contains="Offer"
            ).exists()
        )

    def test_interviewer_cannot_update_application(self):
        self.login(self.interviewer)
        response = self.client.post(
            reverse("application_update", args=[self.application.pk]),
            {"stage": Application.Stage.HIRED},
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_schedules_interview_and_advances_stage(self):
        self.interview.delete()
        self.login(self.recruiter)
        response = self.client.post(
            reverse("interview_add", args=[self.application.pk]),
            {
                "interviewer": self.interviewer.pk,
                "scheduled_at": timezone.localtime(self.starts).strftime("%Y-%m-%dT%H:%M"),
                "duration_minutes": 60,
                "mode": Interview.Mode.VIDEO,
                "meeting_link": "https://meet.example.com/interview",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.stage, Application.Stage.INTERVIEW)
        self.assertTrue(
            Interview.objects.filter(organization=self.org, application=self.application).exists()
        )

    def test_interview_form_hides_foreign_interviewer(self):
        form = InterviewForm(organization=self.org, application=self.application)
        self.assertNotIn(self.foreign_user, form.fields["interviewer"].queryset)

    def test_assigned_interviewer_submits_feedback(self):
        self.login(self.interviewer)
        response = self.client.post(
            reverse("interview_feedback", args=[self.interview.pk]),
            {"status": Interview.Status.COMPLETED, "score": 5, "feedback": "Strong hire."},
        )
        self.assertEqual(response.status_code, 302)
        self.interview.refresh_from_db()
        self.assertEqual(self.interview.status, Interview.Status.COMPLETED)
        self.assertEqual(self.interview.score, 5)

    def test_unassigned_interviewer_cannot_submit_feedback(self):
        self.login(self.second_interviewer)
        response = self.client.post(
            reverse("interview_feedback", args=[self.interview.pk]),
            {"status": Interview.Status.CANCELLED},
        )
        self.assertEqual(response.status_code, 403)

    def test_completed_feedback_requires_score_and_text(self):
        form = InterviewFeedbackForm(
            {"status": Interview.Status.COMPLETED, "score": "", "feedback": ""},
            instance=self.interview,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("score", form.errors)
        self.assertIn("feedback", form.errors)

    def test_foreign_interview_feedback_is_not_found(self):
        self.login()
        self.assertEqual(
            self.client.post(
                reverse("interview_feedback", args=[self.foreign_interview.pk])
            ).status_code,
            404,
        )

    def test_interviewer_list_only_shows_assigned_rows(self):
        Interview.objects.create(
            organization=self.org,
            application=self.application,
            interviewer=self.second_interviewer,
            scheduled_at=self.starts + timedelta(hours=2),
        )
        self.login(self.interviewer)
        response = self.client.get(reverse("interview_list"))
        self.assertContains(response, "interviewer")
        self.assertNotContains(response, "second_interviewer")

    def test_summary_api_is_tenant_scoped(self):
        self.login()
        payload = self.client.get(reverse("api_summary")).json()
        self.assertEqual(payload["workspace"], "Alpha Talent")
        self.assertEqual(payload["open_jobs"], 1)
        self.assertEqual(payload["candidates"], 1)

    def test_jobs_api_is_tenant_scoped(self):
        self.login()
        payload = self.client.get(reverse("api_jobs")).json()["results"]
        self.assertEqual([item["code"] for item in payload], ["ENG-1"])

    def test_applications_api_is_tenant_scoped(self):
        self.login()
        payload = self.client.get(reverse("api_applications")).json()["results"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["candidate"], "Asha")

    def test_interview_api_is_role_and_tenant_scoped(self):
        Interview.objects.create(
            organization=self.org,
            application=self.application,
            interviewer=self.second_interviewer,
            scheduled_at=self.starts + timedelta(hours=2),
        )
        self.login(self.interviewer)
        payload = self.client.get(reverse("api_interviews")).json()["results"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["interviewer"], "interviewer")

    def test_model_pipeline_properties(self):
        self.assertTrue(self.application.is_active)
        self.assertGreaterEqual(self.application.days_in_pipeline, 0)
        self.assertTrue(self.interview.is_upcoming)
        self.assertEqual(self.job.active_application_count, 1)

    def test_activity_note_is_scoped(self):
        self.login(self.interviewer)
        self.client.post(
            reverse("activity_add", args=[self.application.pk]),
            {"message": "Reviewed the candidate profile"},
        )
        self.assertTrue(
            Activity.objects.filter(
                organization=self.org, message="Reviewed the candidate profile"
            ).exists()
        )

    def test_signup_creates_owner_workspace(self):
        response = self.client.post(
            reverse("signup"),
            {
                "organization_name": "Fresh Hiring",
                "username": "newowner",
                "email": "newowner@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        membership = User.objects.get(username="newowner").talent_membership
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(membership.organization.slug, "fresh-hiring")
