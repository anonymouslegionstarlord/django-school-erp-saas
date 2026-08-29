from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    name = models.CharField(max_length=140)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Learning manager"
        INSTRUCTOR = "instructor", "Instructor"
        LEARNER = "learner", "Learner"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="learning_membership")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.LEARNER)
    department = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f"{self.user.username} · {self.get_role_display()}"

    @property
    def can_manage(self):
        return self.role in [self.Role.OWNER, self.Role.MANAGER]

    @property
    def can_author(self):
        return self.role in [self.Role.OWNER, self.Role.MANAGER, self.Role.INSTRUCTOR]


class Course(models.Model):
    class Category(models.TextChoices):
        COMPLIANCE = "compliance", "Compliance"
        ONBOARDING = "onboarding", "Onboarding"
        CUSTOMER = "customer", "Customer success"
        LEADERSHIP = "leadership", "Leadership"
        TECHNICAL = "technical", "Technical"
        OTHER = "other", "Other"

    class Level(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="courses")
    code = models.CharField(max_length=16)
    title = models.CharField(max_length=180)
    summary = models.TextField(max_length=1800)
    category = models.CharField(max_length=16, choices=Category.choices, default=Category.OTHER)
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.BEGINNER)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    instructor = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="instructed_courses"
    )
    estimated_minutes = models.PositiveIntegerField(default=60, validators=[MinValueValidator(1)])
    pass_mark = models.PositiveSmallIntegerField(
        default=70, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    mandatory = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="unique_learning_course_code"
            )
        ]

    def __str__(self):
        return f"{self.code} · {self.title}"

    @property
    def total_module_minutes(self):
        return sum(module.estimated_minutes for module in self.modules.all())

    def clean(self):
        if self.organization_id and self.instructor_id:
            membership = Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.instructor_id
            ).first()
            if membership is None or not membership.can_author:
                raise ValidationError(
                    {"instructor": "Instructor must be an author in this workspace."}
                )


class Module(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="learning_modules"
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=180)
    order = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    content = models.TextField(max_length=6000)
    estimated_minutes = models.PositiveIntegerField(default=15, validators=[MinValueValidator(1)])
    resource_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["course", "order"], name="unique_learning_module_order")
        ]

    def __str__(self):
        return f"{self.course.code}.{self.order} · {self.title}"

    def clean(self):
        if (
            self.organization_id
            and self.course_id
            and self.course.organization_id != self.organization_id
        ):
            raise ValidationError({"course": "Course must belong to this workspace."})


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="enrollments"
    )
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="enrollments")
    learner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="learning_enrollments")
    assigned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="assigned_learning_enrollments"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ASSIGNED)
    due_date = models.DateField(null=True, blank=True)
    score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "due_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "course", "learner"],
                name="unique_learning_course_enrollment",
            )
        ]

    def __str__(self):
        return f"{self.reference} · {self.learner.username} · {self.course.code}"

    @property
    def reference(self):
        return f"ENR-{self.pk:05d}" if self.pk else "ENR-NEW"

    @property
    def completed_module_count(self):
        return self.progress_records.filter(completed=True).count()

    @property
    def total_module_count(self):
        return self.course.modules.count()

    @property
    def progress_percent(self):
        total = self.total_module_count
        return round(self.completed_module_count * 100 / total) if total else 0

    @property
    def is_overdue(self):
        return bool(
            self.due_date
            and self.due_date < timezone.localdate()
            and self.status != self.Status.COMPLETED
        )

    @property
    def passed(self):
        return bool(
            self.status == self.Status.COMPLETED
            and self.score is not None
            and self.score >= self.course.pass_mark
        )

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.course_id
            and self.course.organization_id != self.organization_id
        ):
            errors["course"] = "Course must belong to this workspace."
        if self.organization_id and self.learner_id:
            learner_membership = Membership.objects.filter(
                organization_id=self.organization_id,
                user_id=self.learner_id,
                role=Membership.Role.LEARNER,
            ).exists()
            if not learner_membership:
                errors["learner"] = "Learner must have a learner role in this workspace."
        if (
            self.organization_id
            and self.assigned_by_id
            and not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.assigned_by_id
            ).exists()
        ):
            errors["assigned_by"] = "Assigner must belong to this workspace."
        if errors:
            raise ValidationError(errors)


class LessonProgress(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="lesson_progress"
    )
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="progress_records"
    )
    module = models.ForeignKey(Module, on_delete=models.PROTECT, related_name="progress_records")
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    learner_note = models.CharField(max_length=500, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["module__order"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "module"], name="unique_learning_module_progress"
            )
        ]

    def __str__(self):
        return f"{self.enrollment.reference} · {self.module.title}"

    def save(self, *args, **kwargs):
        if self.completed and self.completed_at is None:
            self.completed_at = timezone.now()
        elif not self.completed:
            self.completed_at = None
        return super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.enrollment_id
            and self.enrollment.organization_id != self.organization_id
        ):
            errors["enrollment"] = "Enrollment must belong to this workspace."
        if (
            self.organization_id
            and self.module_id
            and self.module.organization_id != self.organization_id
        ):
            errors["module"] = "Module must belong to this workspace."
        if (
            self.enrollment_id
            and self.module_id
            and self.enrollment.course_id != self.module.course_id
        ):
            errors["module"] = "Module must belong to the enrolled course."
        if errors:
            raise ValidationError(errors)


class Activity(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="learning_activities"
    )
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="learning_activities")
    message = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "activities"

    def __str__(self):
        return self.message

    def clean(self):
        errors = {}
        if (
            self.organization_id
            and self.enrollment_id
            and self.enrollment.organization_id != self.organization_id
        ):
            errors["enrollment"] = "Enrollment must belong to this workspace."
        if (
            self.organization_id
            and self.actor_id
            and not Membership.objects.filter(
                organization_id=self.organization_id, user_id=self.actor_id
            ).exists()
        ):
            errors["actor"] = "Actor must belong to this workspace."
        if errors:
            raise ValidationError(errors)
