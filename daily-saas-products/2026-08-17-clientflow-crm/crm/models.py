from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="membership")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.MEMBER)


class Contact(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=120)
    company = models.CharField(max_length=120, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["organization", "email"], name="unique_contact_email_per_org")]

    def __str__(self):
        return self.name


class Deal(models.Model):
    class Stage(models.TextChoices):
        LEAD = "lead", "Lead"
        QUALIFIED = "qualified", "Qualified"
        PROPOSAL = "proposal", "Proposal"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="deals")
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="deals")
    title = models.CharField(max_length=160)
    value = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.LEAD)
    expected_close = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Activity(models.Model):
    class Kind(models.TextChoices):
        CALL = "call", "Call"
        EMAIL = "email", "Email"
        MEETING = "meeting", "Meeting"
        NOTE = "note", "Note"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="activities")
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="activities")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    notes = models.TextField(max_length=1000)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
