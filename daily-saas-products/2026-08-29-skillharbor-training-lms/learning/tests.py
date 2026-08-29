from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .context_processors import workspace
from .forms import CourseForm, EnrollmentForm, GradeForm, ModuleForm
from .models import (
    Activity,
    Course,
    Enrollment,
    LessonProgress,
    Membership,
    Module,
    Organization,
)


class SkillHarborTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name="Acme Academy", slug="acme")
        cls.other_organization = Organization.objects.create(name="Other Academy", slug="other")
        cls.owner = cls.make_user("owner", cls.organization, Membership.Role.OWNER, "Owner", "User")
        cls.manager = cls.make_user(
            "manager", cls.organization, Membership.Role.MANAGER, "Manager", "User"
        )
        cls.instructor = cls.make_user(
            "instructor",
            cls.organization,
            Membership.Role.INSTRUCTOR,
            "Ines",
            "Trainer",
        )
        cls.second_instructor = cls.make_user(
            "second_instructor",
            cls.organization,
            Membership.Role.INSTRUCTOR,
            "Sam",
            "Coach",
        )
        cls.learner = cls.make_user(
            "learner", cls.organization, Membership.Role.LEARNER, "Lee", "Learner"
        )
        cls.learner_two = cls.make_user(
            "learner_two", cls.organization, Membership.Role.LEARNER, "Ari", "Learner"
        )
        cls.other_owner = cls.make_user(
            "other_owner",
            cls.other_organization,
            Membership.Role.OWNER,
            "Other",
            "Owner",
        )
        cls.other_instructor = cls.make_user(
            "other_instructor",
            cls.other_organization,
            Membership.Role.INSTRUCTOR,
            "Other",
            "Trainer",
        )
        cls.other_learner = cls.make_user(
            "other_learner",
            cls.other_organization,
            Membership.Role.LEARNER,
            "Other",
            "Learner",
        )

        cls.course = Course.objects.create(
            organization=cls.organization,
            code="SEC-101",
            title="Security essentials",
            summary="Safe information handling.",
            category=Course.Category.COMPLIANCE,
            level=Course.Level.BEGINNER,
            status=Course.Status.PUBLISHED,
            instructor=cls.instructor,
            estimated_minutes=45,
            pass_mark=80,
            mandatory=True,
        )
        cls.module_one = Module.objects.create(
            organization=cls.organization,
            course=cls.course,
            title="Phishing",
            order=1,
            content="Inspect links and sender identity.",
            estimated_minutes=15,
        )
        cls.module_two = Module.objects.create(
            organization=cls.organization,
            course=cls.course,
            title="Data handling",
            order=2,
            content="Use approved storage and least privilege.",
            estimated_minutes=20,
        )
        cls.second_course = Course.objects.create(
            organization=cls.organization,
            code="COACH-1",
            title="Coaching skills",
            summary="Practical coaching conversations.",
            category=Course.Category.LEADERSHIP,
            status=Course.Status.PUBLISHED,
            instructor=cls.second_instructor,
            estimated_minutes=30,
            pass_mark=70,
        )
        cls.second_module = Module.objects.create(
            organization=cls.organization,
            course=cls.second_course,
            title="Ask first",
            order=1,
            content="Ask before advising.",
            estimated_minutes=10,
        )
        cls.other_course = Course.objects.create(
            organization=cls.other_organization,
            code="OTHER-1",
            title="Private other course",
            summary="Must never leak.",
            status=Course.Status.PUBLISHED,
            instructor=cls.other_instructor,
            estimated_minutes=30,
            pass_mark=70,
        )
        cls.other_module = Module.objects.create(
            organization=cls.other_organization,
            course=cls.other_course,
            title="Private module",
            order=1,
            content="Private.",
            estimated_minutes=10,
        )
        cls.enrollment = Enrollment.objects.create(
            organization=cls.organization,
            course=cls.course,
            learner=cls.learner,
            assigned_by=cls.manager,
            due_date=timezone.localdate() + timedelta(days=5),
        )
        cls.progress_one = LessonProgress.objects.create(
            organization=cls.organization,
            enrollment=cls.enrollment,
            module=cls.module_one,
        )
        cls.progress_two = LessonProgress.objects.create(
            organization=cls.organization,
            enrollment=cls.enrollment,
            module=cls.module_two,
        )
        cls.other_enrollment = Enrollment.objects.create(
            organization=cls.other_organization,
            course=cls.other_course,
            learner=cls.other_learner,
            assigned_by=cls.other_owner,
        )
        LessonProgress.objects.create(
            organization=cls.other_organization,
            enrollment=cls.other_enrollment,
            module=cls.other_module,
        )

    @classmethod
    def make_user(cls, username, organization, role, first_name, last_name):
        user = User.objects.create_user(
            username=username,
            password="StrongPass123!",
            first_name=first_name,
            last_name=last_name,
        )
        Membership.objects.create(
            user=user,
            organization=organization,
            role=role,
            department="Testing",
        )
        return user

    def login(self, user):
        self.client.force_login(user)

    def test_public_landing_and_authentication_redirects(self):
        self.assertEqual(self.client.get(reverse("landing")).status_code, 200)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assertTrue(self.client.login(username="learner", password="StrongPass123!"))
        self.assertRedirects(self.client.get(reverse("landing")), reverse("dashboard"))

    def test_signup_creates_owner_workspace_and_starter_course(self):
        response = self.client.post(
            reverse("signup"),
            {
                "organization_name": "Bright Path",
                "username": "new_owner",
                "email": "owner@bright.test",
                "password1": "A-Strong-New-Pass-2026!",
                "password2": "A-Strong-New-Pass-2026!",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="new_owner")
        self.assertEqual(user.learning_membership.role, Membership.Role.OWNER)
        self.assertEqual(user.learning_membership.organization.name, "Bright Path")
        course = Course.objects.get(organization=user.learning_membership.organization)
        self.assertEqual(course.modules.count(), 1)
        self.assertEqual(course.status, Course.Status.DRAFT)

    def test_signup_generates_unique_workspace_slug(self):
        response = self.client.post(
            reverse("signup"),
            {
                "organization_name": "Acme",
                "username": "another_owner",
                "email": "another@acme.test",
                "password1": "Another-Strong-Pass-2026!",
                "password2": "Another-Strong-Pass-2026!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Organization.objects.filter(slug="acme-2").exists())

    def test_account_without_membership_is_forbidden(self):
        user = User.objects.create_user(username="orphan", password="StrongPass123!")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)
        self.assertEqual(workspace(SimpleNamespace(user=user)), {})

    def test_dashboard_works_for_every_role(self):
        for user in [self.owner, self.manager, self.instructor, self.learner]:
            with self.subTest(user=user.username):
                client = Client()
                client.force_login(user)
                response = client.get(reverse("dashboard"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "SkillHarbor")

    def test_membership_capabilities(self):
        self.assertTrue(self.owner.learning_membership.can_manage)
        self.assertTrue(self.manager.learning_membership.can_author)
        self.assertTrue(self.instructor.learning_membership.can_author)
        self.assertFalse(self.learner.learning_membership.can_author)

    def test_course_rejects_cross_tenant_or_learner_instructor(self):
        cross_tenant = Course(
            organization=self.organization,
            code="BAD-1",
            title="Bad",
            summary="Bad relation",
            instructor=self.other_instructor,
            estimated_minutes=10,
        )
        with self.assertRaises(ValidationError):
            cross_tenant.full_clean()
        learner_author = Course(
            organization=self.organization,
            code="BAD-2",
            title="Bad",
            summary="Bad role",
            instructor=self.learner,
            estimated_minutes=10,
        )
        with self.assertRaises(ValidationError):
            learner_author.full_clean()

    def test_module_rejects_cross_tenant_course(self):
        module = Module(
            organization=self.organization,
            course=self.other_course,
            title="Leak",
            order=2,
            content="No",
            estimated_minutes=5,
        )
        with self.assertRaises(ValidationError):
            module.full_clean()

    def test_enrollment_rejects_cross_tenant_relations_and_nonlearner(self):
        enrollment = Enrollment(
            organization=self.organization,
            course=self.other_course,
            learner=self.other_learner,
            assigned_by=self.other_owner,
        )
        with self.assertRaises(ValidationError) as context:
            enrollment.full_clean()
        self.assertIn("course", context.exception.message_dict)
        self.assertIn("learner", context.exception.message_dict)
        self.assertIn("assigned_by", context.exception.message_dict)
        enrollment = Enrollment(
            organization=self.organization,
            course=self.course,
            learner=self.manager,
            assigned_by=self.owner,
        )
        with self.assertRaises(ValidationError):
            enrollment.full_clean()

    def test_progress_and_activity_reject_cross_tenant_relations(self):
        progress = LessonProgress(
            organization=self.organization,
            enrollment=self.enrollment,
            module=self.other_module,
        )
        with self.assertRaises(ValidationError):
            progress.full_clean()
        activity = Activity(
            organization=self.organization,
            enrollment=self.enrollment,
            actor=self.other_owner,
            message="Leak",
        )
        with self.assertRaises(ValidationError):
            activity.full_clean()

    def test_progress_timestamp_and_enrollment_metrics(self):
        self.progress_one.completed = True
        self.progress_one.save()
        self.assertIsNotNone(self.progress_one.completed_at)
        self.assertEqual(self.enrollment.completed_module_count, 1)
        self.assertEqual(self.enrollment.total_module_count, 2)
        self.assertEqual(self.enrollment.progress_percent, 50)
        self.assertEqual(self.course.total_module_minutes, 35)
        self.progress_one.completed = False
        self.progress_one.save()
        self.assertIsNone(self.progress_one.completed_at)

    def test_overdue_and_passed_properties(self):
        self.enrollment.due_date = timezone.localdate() - timedelta(days=1)
        self.assertTrue(self.enrollment.is_overdue)
        self.enrollment.status = Enrollment.Status.COMPLETED
        self.enrollment.score = 85
        self.assertFalse(self.enrollment.is_overdue)
        self.assertTrue(self.enrollment.passed)
        self.enrollment.score = 70
        self.assertFalse(self.enrollment.passed)

    def test_unique_course_code_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Course.objects.create(
                organization=self.organization,
                code=self.course.code,
                title="Duplicate",
                summary="Duplicate",
                instructor=self.instructor,
                estimated_minutes=20,
            )

    def test_course_form_scopes_instructors_and_publishing(self):
        form = CourseForm(
            organization=self.organization,
            user=self.owner,
            data={
                "code": "new-1",
                "title": "New",
                "summary": "New course",
                "category": Course.Category.OTHER,
                "level": Course.Level.BEGINNER,
                "status": Course.Status.DRAFT,
                "instructor": self.instructor.pk,
                "estimated_minutes": 30,
                "pass_mark": 70,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["code"], "NEW-1")
        self.assertNotIn(self.other_instructor, form.fields["instructor"].queryset)
        instructor_form = CourseForm(
            organization=self.organization,
            user=self.instructor,
        )
        self.assertEqual(list(instructor_form.fields["instructor"].queryset), [self.instructor])
        publish_form = CourseForm(
            organization=self.organization,
            user=self.owner,
            data={
                "code": "NEW-2",
                "title": "New",
                "summary": "No module",
                "category": Course.Category.OTHER,
                "level": Course.Level.BEGINNER,
                "status": Course.Status.PUBLISHED,
                "instructor": self.instructor.pk,
                "estimated_minutes": 30,
                "pass_mark": 70,
            },
        )
        self.assertFalse(publish_form.is_valid())

    def test_module_and_enrollment_forms_reject_duplicates(self):
        module_form = ModuleForm(
            course=self.course,
            data={
                "title": "Duplicate order",
                "order": 1,
                "content": "Duplicate",
                "estimated_minutes": 10,
                "resource_url": "",
            },
        )
        self.assertFalse(module_form.is_valid())
        enrollment_form = EnrollmentForm(
            organization=self.organization,
            user=self.manager,
            data={
                "course": self.course.pk,
                "learner": self.learner.pk,
                "due_date": "",
            },
        )
        self.assertFalse(enrollment_form.is_valid())
        self.assertNotIn(self.other_course, enrollment_form.fields["course"].queryset)
        self.assertNotIn(self.other_learner, enrollment_form.fields["learner"].queryset)

    def test_instructor_enrollment_form_contains_only_owned_courses(self):
        form = EnrollmentForm(organization=self.organization, user=self.instructor)
        self.assertIn(self.course, form.fields["course"].queryset)
        self.assertNotIn(self.second_course, form.fields["course"].queryset)

    def test_grade_form_requires_feedback_below_pass_mark(self):
        form = GradeForm({"score": 60, "note": ""}, pass_mark=80)
        self.assertFalse(form.is_valid())
        self.assertTrue(
            GradeForm({"score": 60, "note": "Review the material."}, pass_mark=80).is_valid()
        )
        self.assertFalse(GradeForm({"score": 120, "note": "No"}, pass_mark=80).is_valid())

    def test_learner_cannot_create_courses_or_assignments(self):
        self.login(self.learner)
        self.assertEqual(self.client.get(reverse("course_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("enrollment_create")).status_code, 403)

    def test_owner_and_instructor_can_create_courses(self):
        for user, code in [(self.owner, "OWN-1"), (self.instructor, "INS-1")]:
            with self.subTest(user=user.username):
                client = Client()
                client.force_login(user)
                response = client.post(
                    reverse("course_create"),
                    {
                        "code": code,
                        "title": f"{code} course",
                        "summary": "A useful new course.",
                        "category": Course.Category.TECHNICAL,
                        "level": Course.Level.BEGINNER,
                        "status": Course.Status.DRAFT,
                        "instructor": (self.instructor.pk if user == self.owner else user.pk),
                        "estimated_minutes": 30,
                        "pass_mark": 70,
                        "mandatory": "",
                    },
                )
                self.assertEqual(response.status_code, 302)
                self.assertTrue(
                    Course.objects.filter(organization=self.organization, code=code).exists()
                )

    def test_instructor_can_edit_own_course_but_not_another(self):
        self.login(self.instructor)
        response = self.client.post(
            reverse("course_edit", args=[self.course.pk]),
            {
                "code": self.course.code,
                "title": "Security essentials updated",
                "summary": self.course.summary,
                "category": self.course.category,
                "level": self.course.level,
                "status": self.course.status,
                "instructor": self.instructor.pk,
                "estimated_minutes": self.course.estimated_minutes,
                "pass_mark": self.course.pass_mark,
                "mandatory": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.course.refresh_from_db()
        self.assertEqual(self.course.title, "Security essentials updated")
        self.assertEqual(
            self.client.get(reverse("course_edit", args=[self.second_course.pk])).status_code,
            403,
        )

    def test_course_and_enrollment_detail_are_tenant_isolated(self):
        self.login(self.owner)
        self.assertEqual(
            self.client.get(reverse("course_detail", args=[self.other_course.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("enrollment_detail", args=[self.other_enrollment.pk])
            ).status_code,
            404,
        )

    def test_learner_sees_only_enrolled_course(self):
        self.login(self.learner)
        response = self.client.get(reverse("course_list"))
        self.assertContains(response, self.course.title)
        self.assertNotContains(response, self.second_course.title)
        self.assertEqual(
            self.client.get(reverse("course_detail", args=[self.second_course.pk])).status_code,
            404,
        )

    def test_publish_requires_module_and_blocks_archived_course(self):
        draft = Course.objects.create(
            organization=self.organization,
            code="DRAFT-1",
            title="Draft",
            summary="Draft course",
            instructor=self.instructor,
            estimated_minutes=20,
        )
        self.login(self.owner)
        self.client.post(reverse("course_publish", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertEqual(draft.status, Course.Status.DRAFT)
        Module.objects.create(
            organization=self.organization,
            course=draft,
            title="Module",
            order=1,
            content="Content",
            estimated_minutes=10,
        )
        self.client.post(reverse("course_publish", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertEqual(draft.status, Course.Status.PUBLISHED)
        draft.status = Course.Status.ARCHIVED
        draft.save()
        self.client.post(reverse("course_publish", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertEqual(draft.status, Course.Status.ARCHIVED)

    def test_module_create_and_edit_workflow(self):
        self.login(self.instructor)
        response = self.client.post(
            reverse("module_create", args=[self.course.pk]),
            {
                "title": "Incident response",
                "order": 3,
                "content": "Report immediately.",
                "estimated_minutes": 10,
                "resource_url": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        module = Module.objects.get(course=self.course, order=3)
        response = self.client.post(
            reverse("module_edit", args=[self.course.pk, module.pk]),
            {
                "title": "Incident response updated",
                "order": 3,
                "content": "Preserve evidence and report immediately.",
                "estimated_minutes": 12,
                "resource_url": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        module.refresh_from_db()
        self.assertEqual(module.estimated_minutes, 12)

    def test_enrollment_creation_builds_module_scope_and_activity(self):
        self.login(self.manager)
        response = self.client.post(
            reverse("enrollment_create"),
            {
                "course": self.course.pk,
                "learner": self.learner_two.pk,
                "due_date": timezone.localdate() + timedelta(days=10),
            },
        )
        self.assertEqual(response.status_code, 302)
        enrollment = Enrollment.objects.get(course=self.course, learner=self.learner_two)
        self.assertEqual(enrollment.progress_records.count(), 2)
        self.assertEqual(enrollment.activities.count(), 1)

    def test_enrollment_list_is_role_scoped_and_filterable(self):
        other_assignment = Enrollment.objects.create(
            organization=self.organization,
            course=self.second_course,
            learner=self.learner_two,
            assigned_by=self.manager,
            due_date=timezone.localdate() - timedelta(days=1),
        )
        LessonProgress.objects.create(
            organization=self.organization,
            enrollment=other_assignment,
            module=self.second_module,
        )
        self.login(self.learner)
        response = self.client.get(reverse("enrollment_list"))
        self.assertContains(response, self.enrollment.reference)
        self.assertNotContains(response, other_assignment.reference)
        self.client.force_login(self.instructor)
        response = self.client.get(reverse("enrollment_list"))
        self.assertContains(response, self.enrollment.reference)
        self.assertNotContains(response, other_assignment.reference)
        self.client.force_login(self.manager)
        response = self.client.get(reverse("enrollment_list"), {"overdue": "1"})
        self.assertContains(response, other_assignment.reference)
        self.assertNotContains(response, self.enrollment.reference)

    def test_learner_progress_starts_enrollment_and_records_activity(self):
        self.login(self.learner)
        response = self.client.post(
            reverse("progress_update", args=[self.enrollment.pk, self.progress_one.pk]),
            {"completed": "on", "learner_note": "I understand the examples."},
        )
        self.assertRedirects(response, reverse("enrollment_detail", args=[self.enrollment.pk]))
        self.progress_one.refresh_from_db()
        self.enrollment.refresh_from_db()
        self.assertTrue(self.progress_one.completed)
        self.assertIsNotNone(self.progress_one.completed_at)
        self.assertEqual(self.enrollment.status, Enrollment.Status.IN_PROGRESS)
        self.assertIsNotNone(self.enrollment.started_at)
        self.assertTrue(
            self.enrollment.activities.filter(message__icontains="marked completed").exists()
        )

    def test_learner_cannot_update_another_assignment(self):
        enrollment = Enrollment.objects.create(
            organization=self.organization,
            course=self.second_course,
            learner=self.learner_two,
            assigned_by=self.manager,
        )
        progress = LessonProgress.objects.create(
            organization=self.organization,
            enrollment=enrollment,
            module=self.second_module,
        )
        self.login(self.learner)
        response = self.client.post(
            reverse("progress_update", args=[enrollment.pk, progress.pk]),
            {"completed": "on"},
        )
        self.assertEqual(response.status_code, 404)

    def test_instructor_can_update_owned_course_progress(self):
        self.login(self.instructor)
        response = self.client.post(
            reverse("progress_update", args=[self.enrollment.pk, self.progress_one.pk]),
            {"completed": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.progress_one.refresh_from_db()
        self.assertTrue(self.progress_one.completed)

    def test_completed_enrollment_progress_is_read_only(self):
        self.enrollment.status = Enrollment.Status.COMPLETED
        self.enrollment.score = 90
        self.enrollment.save()
        self.login(self.manager)
        response = self.client.post(
            reverse("progress_update", args=[self.enrollment.pk, self.progress_one.pk]),
            {"completed": "on"},
        )
        self.assertEqual(response.status_code, 403)

    def test_grading_requires_all_modules(self):
        self.login(self.instructor)
        response = self.client.post(
            reverse("enrollment_grade", args=[self.enrollment.pk]),
            {"score": 90, "note": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.enrollment.refresh_from_db()
        self.assertIsNone(self.enrollment.score)
        self.assertEqual(self.enrollment.status, Enrollment.Status.ASSIGNED)

    def test_failed_grade_keeps_enrollment_in_progress(self):
        LessonProgress.objects.filter(enrollment=self.enrollment).update(
            completed=True, completed_at=timezone.now()
        )
        self.login(self.instructor)
        self.client.post(
            reverse("enrollment_grade", args=[self.enrollment.pk]),
            {"score": 65, "note": "Review data-handling scenarios."},
        )
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.score, 65)
        self.assertEqual(self.enrollment.status, Enrollment.Status.IN_PROGRESS)
        self.assertIsNone(self.enrollment.completed_at)

    def test_passing_grade_completes_and_freezes_enrollment(self):
        LessonProgress.objects.filter(enrollment=self.enrollment).update(
            completed=True, completed_at=timezone.now()
        )
        self.login(self.instructor)
        self.client.post(
            reverse("enrollment_grade", args=[self.enrollment.pk]),
            {"score": 88, "note": "Strong result."},
        )
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, Enrollment.Status.COMPLETED)
        self.assertTrue(self.enrollment.passed)
        self.assertIsNotNone(self.enrollment.completed_at)
        response = self.client.post(
            reverse("enrollment_grade", args=[self.enrollment.pk]),
            {"score": 90, "note": ""},
        )
        self.assertEqual(response.status_code, 403)

    def test_learner_cannot_grade(self):
        self.login(self.learner)
        response = self.client.post(
            reverse("enrollment_grade", args=[self.enrollment.pk]),
            {"score": 90, "note": ""},
        )
        self.assertEqual(response.status_code, 403)

    def test_comment_creates_tenant_activity(self):
        self.login(self.learner)
        response = self.client.post(
            reverse("enrollment_comment", args=[self.enrollment.pk]),
            {"message": "I will finish the remaining module tomorrow."},
        )
        self.assertEqual(response.status_code, 302)
        activity = self.enrollment.activities.get(
            message="I will finish the remaining module tomorrow."
        )
        self.assertEqual(activity.organization, self.organization)
        self.assertEqual(activity.actor, self.learner)

    def test_api_requires_authentication_and_returns_summary(self):
        self.assertEqual(self.client.get(reverse("api_summary")).status_code, 302)
        self.login(self.manager)
        response = self.client.get(reverse("api_summary"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workspace"], self.organization.name)
        self.assertEqual(payload["enrollments"], 1)

    def test_learner_apis_are_role_and_tenant_scoped(self):
        self.login(self.learner)
        courses = self.client.get(reverse("api_courses")).json()["results"]
        self.assertEqual([item["code"] for item in courses], [self.course.code])
        enrollments = self.client.get(reverse("api_enrollments")).json()["results"]
        self.assertEqual(len(enrollments), 1)
        serialized = str(enrollments)
        self.assertNotIn(self.other_course.code, serialized)
        response = self.client.get(
            reverse("api_enrollment_detail", args=[self.other_enrollment.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_api_filters_and_enrollment_detail(self):
        self.login(self.manager)
        response = self.client.get(reverse("api_courses"), {"category": Course.Category.COMPLIANCE})
        self.assertEqual(len(response.json()["results"]), 1)
        response = self.client.get(
            reverse("api_enrollments"), {"status": Enrollment.Status.ASSIGNED}
        )
        self.assertEqual(len(response.json()["results"]), 1)
        detail = self.client.get(reverse("api_enrollment_detail", args=[self.enrollment.pk])).json()
        self.assertEqual(detail["course"]["code"], self.course.code)
        self.assertEqual(len(detail["modules"]), 2)
        self.assertEqual(detail["progress"], 0)
