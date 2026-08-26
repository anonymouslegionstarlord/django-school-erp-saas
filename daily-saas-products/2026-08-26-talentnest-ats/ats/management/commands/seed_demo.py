from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from ats.models import (
    Activity,
    Application,
    Candidate,
    Interview,
    JobOpening,
    Membership,
    Organization,
)


class Command(BaseCommand):
    help = "Create an idempotent TalentNest demo workspace"

    def handle(self, *args, **options):
        password = "DemoPass123!"
        organization, _ = Organization.objects.get_or_create(
            slug="northstar-digital", defaults={"name": "Northstar Digital"}
        )
        users = {}
        for username, role, email in [
            ("demo_talent", Membership.Role.OWNER, "talent@example.com"),
            ("demo_recruiter", Membership.Role.RECRUITER, "recruiter@example.com"),
            ("demo_interviewer", Membership.Role.INTERVIEWER, "interviewer@example.com"),
        ]:
            user, _ = User.objects.get_or_create(username=username, defaults={"email": email})
            user.email = email
            user.set_password(password)
            user.save()
            Membership.objects.update_or_create(
                user=user, defaults={"organization": organization, "role": role}
            )
            users[username] = user

        jobs = {}
        for code, title, department, location, kind, status, openings, description in [
            (
                "ENG-101",
                "Backend Python Engineer",
                "Engineering",
                "Bengaluru · Hybrid",
                JobOpening.EmploymentType.FULL_TIME,
                JobOpening.Status.OPEN,
                2,
                "Build reliable Django services, APIs, and data workflows for SaaS products.",
            ),
            (
                "DES-205",
                "Product Designer",
                "Design",
                "Remote · India",
                JobOpening.EmploymentType.FULL_TIME,
                JobOpening.Status.OPEN,
                1,
                "Own product discovery, interaction design, prototypes, and design systems.",
            ),
            (
                "OPS-310",
                "Customer Operations Associate",
                "Operations",
                "Noida · On site",
                JobOpening.EmploymentType.CONTRACT,
                JobOpening.Status.PAUSED,
                3,
                "Support customers, investigate product issues, and improve operating playbooks.",
            ),
        ]:
            job, _ = JobOpening.objects.update_or_create(
                organization=organization,
                code=code,
                defaults={
                    "title": title,
                    "department": department,
                    "location": location,
                    "employment_type": kind,
                    "status": status,
                    "openings": openings,
                    "recruiter": users["demo_recruiter"],
                    "description": description,
                },
            )
            jobs[code] = job

        candidates = {}
        for name, email, company, source, skills in [
            (
                "Asha Mehta",
                "asha@example.com",
                "BrightStack",
                Candidate.Source.LINKEDIN,
                "Python, Django, PostgreSQL, Docker",
            ),
            (
                "Rohan Kapoor",
                "rohan@example.com",
                "PixelMint",
                Candidate.Source.REFERRAL,
                "Product design, Figma, research, design systems",
            ),
            (
                "Sana Iqbal",
                "sana@example.com",
                "CloudArc",
                Candidate.Source.JOB_BOARD,
                "FastAPI, Django REST Framework, AWS",
            ),
            (
                "Neel Verma",
                "neel@example.com",
                "SupportHive",
                Candidate.Source.CAREERS,
                "Customer support, SQL, incident triage",
            ),
        ]:
            candidate, _ = Candidate.objects.update_or_create(
                organization=organization,
                email=email,
                defaults={
                    "name": name,
                    "current_company": company,
                    "source": source,
                    "skills": skills,
                },
            )
            candidates[name] = candidate

        applications = {}
        for candidate_name, code, stage, rating, summary in [
            (
                "Asha Mehta",
                "ENG-101",
                Application.Stage.INTERVIEW,
                5,
                "Strong backend fundamentals and clear system-design communication.",
            ),
            (
                "Sana Iqbal",
                "ENG-101",
                Application.Stage.SCREENING,
                4,
                "Relevant API experience; reviewing production ownership examples.",
            ),
            (
                "Rohan Kapoor",
                "DES-205",
                Application.Stage.OFFER,
                5,
                "Excellent portfolio and collaborative product thinking.",
            ),
            (
                "Neel Verma",
                "OPS-310",
                Application.Stage.APPLIED,
                3,
                "Good support background; role is currently paused.",
            ),
        ]:
            application, _ = Application.objects.update_or_create(
                organization=organization,
                candidate=candidates[candidate_name],
                job=jobs[code],
                defaults={
                    "owner": users["demo_recruiter"],
                    "stage": stage,
                    "rating": rating,
                    "summary": summary,
                },
            )
            applications[candidate_name] = application

        now = timezone.now().replace(second=0, microsecond=0)
        Interview.objects.update_or_create(
            organization=organization,
            application=applications["Asha Mehta"],
            interviewer=users["demo_interviewer"],
            defaults={
                "scheduled_at": now + timedelta(days=2),
                "duration_minutes": 60,
                "mode": Interview.Mode.VIDEO,
                "meeting_link": "https://meet.example.com/talentnest-demo",
                "status": Interview.Status.SCHEDULED,
                "score": None,
                "feedback": "",
            },
        )
        Interview.objects.update_or_create(
            organization=organization,
            application=applications["Rohan Kapoor"],
            interviewer=users["demo_talent"],
            defaults={
                "scheduled_at": now - timedelta(days=3),
                "duration_minutes": 45,
                "mode": Interview.Mode.VIDEO,
                "status": Interview.Status.COMPLETED,
                "score": 5,
                "feedback": "Strong discovery process and thoughtful trade-off decisions.",
            },
        )

        for candidate_name, message in [
            ("Asha Mehta", "Technical interview scheduled"),
            ("Sana Iqbal", "Recruiter screen completed"),
            ("Rohan Kapoor", "Offer approval requested"),
        ]:
            Activity.objects.get_or_create(
                organization=organization,
                application=applications[candidate_name],
                author=users["demo_recruiter"],
                message=message,
            )

        self.stdout.write(self.style.SUCCESS("TalentNest demo ready: demo_talent / DemoPass123!"))
