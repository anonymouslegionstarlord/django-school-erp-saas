from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Attendance, Course, Enrollment, Invoice, Membership, Payment, School, Student, Teacher


class Command(BaseCommand):
    help = "Create or refresh a safe local demo school and sample records."

    @transaction.atomic
    def handle(self, *args, **options):
        username = "demo_admin"
        password = "DemoPass123!"
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"first_name": "Demo", "last_name": "Admin", "email": "demo@example.com"},
        )
        user.set_password(password)
        user.save()

        school, _ = School.objects.update_or_create(
            slug="greenfield-academy",
            defaults={"name": "Greenfield Academy", "email": "hello@greenfield.example", "plan": School.Plan.GROWTH},
        )
        Membership.objects.update_or_create(
            user=user,
            school=school,
            defaults={"role": Membership.Role.OWNER, "is_active": True},
        )

        teacher_specs = [
            ("T-101", "Asha", "Sharma", "asha@greenfield.example", "Mathematics"),
            ("T-102", "Kabir", "Mehta", "kabir@greenfield.example", "Science"),
            ("T-103", "Naina", "Rao", "naina@greenfield.example", "English"),
        ]
        teachers = []
        for employee_id, first, last, email, subject in teacher_specs:
            teacher, _ = Teacher.objects.update_or_create(
                school=school,
                employee_id=employee_id,
                defaults={"first_name": first, "last_name": last, "email": email, "subject": subject},
            )
            teachers.append(teacher)

        course_specs = [
            ("MATH-08", "Mathematics", "Grade 8", teachers[0]),
            ("SCI-08", "General Science", "Grade 8", teachers[1]),
            ("ENG-08", "English Language", "Grade 8", teachers[2]),
        ]
        courses = []
        for code, name, grade, teacher in course_specs:
            course, _ = Course.objects.update_or_create(
                school=school,
                code=code,
                defaults={
                    "name": name,
                    "grade_level": grade,
                    "teacher": teacher,
                    "description": f"Core {grade} {name} course.",
                },
            )
            courses.append(course)

        student_specs = [
            ("GF-2401", "Aarav", "Verma", "Rakesh Verma", "9876500001"),
            ("GF-2402", "Diya", "Singh", "Meera Singh", "9876500002"),
            ("GF-2403", "Ishaan", "Gupta", "Neha Gupta", "9876500003"),
            ("GF-2404", "Myra", "Kapoor", "Amit Kapoor", "9876500004"),
            ("GF-2405", "Vihaan", "Joshi", "Pooja Joshi", "9876500005"),
        ]
        students = []
        for admission, first, last, guardian, phone in student_specs:
            student, _ = Student.objects.update_or_create(
                school=school,
                admission_number=admission,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "guardian_name": guardian,
                    "guardian_phone": phone,
                    "class_name": "Grade 8",
                    "section": "A",
                },
            )
            students.append(student)
            for course in courses:
                Enrollment.objects.get_or_create(school=school, student=student, course=course)

        today = timezone.localdate()
        for index, student in enumerate(students):
            Attendance.objects.update_or_create(
                school=school,
                student=student,
                date=today,
                defaults={
                    "course": courses[0],
                    "status": Attendance.Status.ABSENT if index == 3 else Attendance.Status.PRESENT,
                    "marked_by": user,
                },
            )
            invoice, _ = Invoice.objects.update_or_create(
                school=school,
                student=student,
                title="Term 1 Tuition Fee",
                defaults={"amount": Decimal("18500.00"), "due_date": today + timedelta(days=10)},
            )
            if index < 3:
                payment, created = Payment.objects.get_or_create(
                    invoice=invoice,
                    reference=f"DEMO-{index + 1}",
                    defaults={"amount": Decimal("18500.00"), "method": Payment.Method.UPI, "recorded_by": user},
                )
                if not created:
                    payment.save()
            invoice.refresh_status()

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self.stdout.write(f"Username: {username}")
        self.stdout.write(f"Password: {password}")
