from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from learning.models import (
    Activity,
    Course,
    Enrollment,
    LessonProgress,
    Membership,
    Module,
    Organization,
)


class Command(BaseCommand):
    help = "Create or refresh the SkillHarbor demonstration workspace."

    @transaction.atomic
    def handle(self, *args, **options):
        organization, _ = Organization.objects.update_or_create(
            slug="apex-learning-labs",
            defaults={"name": "Apex Learning Labs"},
        )
        people = [
            (
                "demo_learning",
                "Mira",
                "Shah",
                "mira@example.test",
                Membership.Role.OWNER,
                "People Operations",
                "Head of People",
            ),
            (
                "demo_lnd_manager",
                "Arjun",
                "Mehta",
                "arjun@example.test",
                Membership.Role.MANAGER,
                "Learning and Development",
                "Learning Manager",
            ),
            (
                "demo_instructor",
                "Nina",
                "Rao",
                "nina@example.test",
                Membership.Role.INSTRUCTOR,
                "Enablement",
                "Senior Facilitator",
            ),
            (
                "demo_learner",
                "Kabir",
                "Singh",
                "kabir@example.test",
                Membership.Role.LEARNER,
                "Customer Success",
                "Customer Success Associate",
            ),
        ]
        users = {}
        for username, first_name, last_name, email, role, department, job_title in people:
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "is_active": True,
                },
            )
            user.set_password("DemoPass123!")
            user.save()
            Membership.objects.update_or_create(
                user=user,
                defaults={
                    "organization": organization,
                    "role": role,
                    "department": department,
                    "job_title": job_title,
                },
            )
            users[username] = user

        instructor = users["demo_instructor"]
        manager = users["demo_lnd_manager"]
        learner = users["demo_learner"]

        course_specs = [
            {
                "code": "SEC-101",
                "title": "Security and privacy essentials",
                "summary": (
                    "Recognize common security risks, handle customer data safely, "
                    "and respond correctly when something looks suspicious."
                ),
                "category": Course.Category.COMPLIANCE,
                "level": Course.Level.BEGINNER,
                "status": Course.Status.PUBLISHED,
                "estimated_minutes": 55,
                "pass_mark": 80,
                "mandatory": True,
                "modules": [
                    (
                        "Spot phishing before it spreads",
                        "Inspect sender identity, links, urgency, and unexpected attachments. "
                        "When uncertain, report the message through the approved security channel.",
                        18,
                    ),
                    (
                        "Handle customer data with care",
                        "Use least-privilege access, approved storage, clean-desk practices, "
                        "and the correct retention path for customer information.",
                        20,
                    ),
                    (
                        "Respond to a suspected incident",
                        "Stop, preserve evidence, contact the response team, and avoid actions "
                        "that could destroy logs or increase exposure.",
                        17,
                    ),
                ],
            },
            {
                "code": "CS-204",
                "title": "Customer de-escalation playbook",
                "summary": (
                    "Use practical listening, acknowledgement, and solution framing "
                    "to guide difficult customer conversations toward resolution."
                ),
                "category": Course.Category.CUSTOMER,
                "level": Course.Level.INTERMEDIATE,
                "status": Course.Status.PUBLISHED,
                "estimated_minutes": 70,
                "pass_mark": 75,
                "mandatory": False,
                "modules": [
                    (
                        "Listen for the real concern",
                        "Separate the stated problem from the customer's underlying impact. "
                        "Reflect the concern in neutral language before proposing a fix.",
                        20,
                    ),
                    (
                        "Lower the temperature",
                        "Acknowledge emotion without accepting inaccurate claims. Set a calm "
                        "pace, make ownership visible, and avoid defensive language.",
                        25,
                    ),
                    (
                        "Close with accountable next steps",
                        "Confirm the agreed outcome, owner, timing, follow-up channel, and "
                        "what the customer should expect if the plan changes.",
                        25,
                    ),
                ],
            },
            {
                "code": "LD-310",
                "title": "Coaching conversations for new managers",
                "summary": (
                    "Prepare and lead short coaching conversations that turn observation "
                    "into clear, respectful, and measurable next steps."
                ),
                "category": Course.Category.LEADERSHIP,
                "level": Course.Level.INTERMEDIATE,
                "status": Course.Status.PUBLISHED,
                "estimated_minutes": 65,
                "pass_mark": 70,
                "mandatory": False,
                "modules": [
                    (
                        "Prepare with evidence",
                        "Bring specific observations, explain their impact, and remove assumptions "
                        "about intent before starting the conversation.",
                        20,
                    ),
                    (
                        "Ask before advising",
                        "Use open questions to understand context and invite the employee to "
                        "identify options before you offer your own.",
                        20,
                    ),
                    (
                        "Agree on one observable commitment",
                        "End with a small action, a success measure, support from the manager, "
                        "and a date to review progress.",
                        25,
                    ),
                ],
            },
            {
                "code": "AI-115",
                "title": "Responsible AI at work",
                "summary": (
                    "A draft program for reviewing data sensitivity, human oversight, "
                    "and output quality when employees use generative AI tools."
                ),
                "category": Course.Category.COMPLIANCE,
                "level": Course.Level.BEGINNER,
                "status": Course.Status.DRAFT,
                "estimated_minutes": 45,
                "pass_mark": 80,
                "mandatory": True,
                "modules": [
                    (
                        "Classify before prompting",
                        "Identify confidential, personal, regulated, or customer-owned data "
                        "before entering information into any AI-assisted workflow.",
                        15,
                    ),
                    (
                        "Verify before sharing",
                        "Check facts, calculations, tone, sources, and permissions. Human review "
                        "remains accountable for the final work product.",
                        15,
                    ),
                ],
            },
        ]

        courses = {}
        for spec in course_specs:
            module_specs = spec.pop("modules")
            course, _ = Course.objects.update_or_create(
                organization=organization,
                code=spec["code"],
                defaults={"instructor": instructor, **spec},
            )
            courses[course.code] = course
            for order, (title, content, minutes) in enumerate(module_specs, start=1):
                Module.objects.update_or_create(
                    course=course,
                    order=order,
                    defaults={
                        "organization": organization,
                        "title": title,
                        "content": content,
                        "estimated_minutes": minutes,
                    },
                )

        today = timezone.localdate()
        enrollment_specs = [
            (
                "SEC-101",
                today + timedelta(days=5),
                Enrollment.Status.IN_PROGRESS,
                None,
                2,
            ),
            (
                "CS-204",
                today - timedelta(days=4),
                Enrollment.Status.COMPLETED,
                92,
                3,
            ),
            (
                "LD-310",
                today - timedelta(days=2),
                Enrollment.Status.ASSIGNED,
                None,
                0,
            ),
        ]
        for code, due_date, status, score, completed_modules in enrollment_specs:
            course = courses[code]
            now = timezone.now()
            enrollment, _ = Enrollment.objects.update_or_create(
                organization=organization,
                course=course,
                learner=learner,
                defaults={
                    "assigned_by": manager,
                    "due_date": due_date,
                    "status": status,
                    "score": score,
                    "started_at": now if status != Enrollment.Status.ASSIGNED else None,
                    "completed_at": (
                        now - timedelta(days=4) if status == Enrollment.Status.COMPLETED else None
                    ),
                },
            )
            for module in course.modules.all():
                completed = module.order <= completed_modules
                LessonProgress.objects.update_or_create(
                    enrollment=enrollment,
                    module=module,
                    defaults={
                        "organization": organization,
                        "completed": completed,
                        "completed_at": (
                            now - timedelta(days=max(1, completed_modules - module.order + 1))
                            if completed
                            else None
                        ),
                        "learner_note": (
                            "Useful examples; I added the checklist to my workflow."
                            if completed and module.order == 1
                            else ""
                        ),
                    },
                )
            Activity.objects.get_or_create(
                organization=organization,
                enrollment=enrollment,
                actor=manager,
                message=f"{course.code} assigned to {learner.get_full_name()}",
            )
            if completed_modules:
                Activity.objects.get_or_create(
                    organization=organization,
                    enrollment=enrollment,
                    actor=learner,
                    message=f"Completed {completed_modules} of {course.modules.count()} modules",
                )
            if status == Enrollment.Status.COMPLETED:
                Activity.objects.get_or_create(
                    organization=organization,
                    enrollment=enrollment,
                    actor=instructor,
                    message=f"Final score {score}% — passed and completed",
                )

        self.stdout.write(
            self.style.SUCCESS(
                "SkillHarbor demo ready: demo_learning / demo_lnd_manager / "
                "demo_instructor / demo_learner (password: DemoPass123!)"
            )
        )
