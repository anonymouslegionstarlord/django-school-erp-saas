from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        RECRUITER = "recruiter", "Recruiter"
        INTERVIEWER = "interviewer", "Interviewer"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="talent_membership")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.INTERVIEWER)

    @property
    def can_manage(self):
        return self.role in [self.Role.OWNER, self.Role.RECRUITER]


class JobOpening(models.Model):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full time"
        PART_TIME = "part_time", "Part time"
        CONTRACT = "contract", "Contract"
        INTERNSHIP = "internship", "Internship"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="job_openings"
    )
    code = models.CharField(max_length=30)
    title = models.CharField(max_length=160)
    department = models.CharField(max_length=100)
    location = models.CharField(max_length=120)
    employment_type = models.CharField(
        max_length=12, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    openings = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    recruiter = models.ForeignKey(User, on_delete=models.PROTECT, related_name="recruiting_jobs")
    description = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="unique_talent_job_code_per_org"
            )
        ]

    @property
    def active_application_count(self):
        return self.applications.exclude(
            stage__in=[Application.Stage.HIRED, Application.Stage.REJECTED]
        ).count()

    def clean(self):
        if (
            self.recruiter_id
            and not Membership.objects.filter(
                user_id=self.recruiter_id, organization_id=self.organization_id
            ).exists()
        ):
            raise ValidationError({"recruiter": "Recruiter must belong to this workspace."})

    def __str__(self):
        return f"{self.code} · {self.title}"


class Candidate(models.Model):
    class Source(models.TextChoices):
        LINKEDIN = "linkedin", "LinkedIn"
        REFERRAL = "referral", "Employee referral"
        CAREERS = "careers", "Careers page"
        JOB_BOARD = "job_board", "Job board"
        OTHER = "other", "Other"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="candidates"
    )
    name = models.CharField(max_length=140)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    current_company = models.CharField(max_length=140, blank=True)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.CAREERS)
    skills = models.TextField(max_length=1200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"], name="unique_talent_candidate_email_per_org"
            )
        ]

    def __str__(self):
        return self.name


class Application(models.Model):
    class Stage(models.TextChoices):
        APPLIED = "applied", "Applied"
        SCREENING = "screening", "Screening"
        INTERVIEW = "interview", "Interview"
        OFFER = "offer", "Offer"
        HIRED = "hired", "Hired"
        REJECTED = "rejected", "Rejected"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="applications"
    )
    job = models.ForeignKey(JobOpening, on_delete=models.PROTECT, related_name="applications")
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT, related_name="applications")
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_applications")
    stage = models.CharField(max_length=12, choices=Stage.choices, default=Stage.APPLIED)
    rating = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    summary = models.TextField(max_length=1500, blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "job", "candidate"],
                name="unique_talent_candidate_application",
            )
        ]

    @property
    def is_active(self):
        return self.stage not in [self.Stage.HIRED, self.Stage.REJECTED]

    @property
    def days_in_pipeline(self):
        applied_on = timezone.localtime(self.applied_at).date()
        return max((timezone.localdate() - applied_on).days, 0)

    def clean(self):
        errors = {}
        if self.job_id and self.job.organization_id != self.organization_id:
            errors["job"] = "Job must belong to this workspace."
        if self.candidate_id and self.candidate.organization_id != self.organization_id:
            errors["candidate"] = "Candidate must belong to this workspace."
        if (
            self.owner_id
            and not Membership.objects.filter(
                user_id=self.owner_id, organization_id=self.organization_id
            ).exists()
        ):
            errors["owner"] = "Owner must belong to this workspace."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.candidate} for {self.job.title}"


class Interview(models.Model):
    class Mode(models.TextChoices):
        VIDEO = "video", "Video"
        PHONE = "phone", "Phone"
        ONSITE = "onsite", "On site"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="interviews"
    )
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="interviews"
    )
    interviewer = models.ForeignKey(User, on_delete=models.PROTECT, related_name="interviews")
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(
        default=45, validators=[MinValueValidator(15), MaxValueValidator(240)]
    )
    mode = models.CharField(max_length=8, choices=Mode.choices, default=Mode.VIDEO)
    meeting_link = models.URLField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED)
    score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    feedback = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "interviewer", "scheduled_at"],
                name="unique_talent_interviewer_slot",
            )
        ]

    @property
    def is_upcoming(self):
        return self.status == self.Status.SCHEDULED and self.scheduled_at >= timezone.now()

    def clean(self):
        errors = {}
        if self.application_id and self.application.organization_id != self.organization_id:
            errors["application"] = "Application must belong to this workspace."
        if (
            self.interviewer_id
            and not Membership.objects.filter(
                user_id=self.interviewer_id, organization_id=self.organization_id
            ).exists()
        ):
            errors["interviewer"] = "Interviewer must belong to this workspace."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.application.candidate} · {self.get_mode_display()}"


class Activity(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="talent_activities"
    )
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="activities"
    )
    author = models.ForeignKey(User, on_delete=models.PROTECT, related_name="talent_activities")
    message = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message
