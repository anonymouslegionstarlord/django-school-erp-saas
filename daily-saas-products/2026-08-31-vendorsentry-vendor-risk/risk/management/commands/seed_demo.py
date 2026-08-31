from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from risk.models import (
    Activity,
    Assessment,
    AssessmentControl,
    Finding,
    Membership,
    Organization,
    Vendor,
)
from risk.services import create_baseline_controls


class Command(BaseCommand):
    help = "Create or refresh the idempotent VendorSentry demonstration workspace."

    password = "DemoPass123!"

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        now = timezone.now()
        organization, _ = Organization.objects.update_or_create(
            slug="atlas-commerce",
            defaults={"name": "Atlas Commerce Risk Office"},
        )
        users = {
            "owner": self._user(
                organization,
                username="demo_risk",
                first_name="Avery",
                last_name="Morgan",
                email="avery@example.com",
                role=Membership.Role.OWNER,
                team="Governance",
                title="Chief risk officer",
            ),
            "manager": self._user(
                organization,
                username="demo_risk_manager",
                first_name="Leena",
                last_name="Kapoor",
                email="leena@example.com",
                role=Membership.Role.RISK_MANAGER,
                team="Third-party risk",
                title="Vendor risk manager",
            ),
            "analyst": self._user(
                organization,
                username="demo_analyst",
                first_name="Jonah",
                last_name="Reed",
                email="jonah@example.com",
                role=Membership.Role.ANALYST,
                team="Third-party risk",
                title="Risk analyst",
            ),
            "viewer": self._user(
                organization,
                username="demo_auditor",
                first_name="Mina",
                last_name="Costa",
                email="mina@example.com",
                role=Membership.Role.VIEWER,
                team="Internal audit",
                title="Internal auditor",
            ),
        }

        vendors = {
            "nimbus": self._vendor(
                organization,
                name="NimbusCloud",
                slug="nimbuscloud",
                category=Vendor.Category.CLOUD,
                criticality=Vendor.Criticality.CRITICAL,
                status=Vendor.Status.ACTIVE,
                description=(
                    "Hosts the customer application, managed databases, and production backups."
                ),
                owner=users["owner"],
                pii=True,
                production=True,
                finance=False,
                spend="2400000.00",
                contract_expiry=today + timedelta(days=155),
                next_review=today + timedelta(days=345),
            ),
            "ledger": self._vendor(
                organization,
                name="LedgerPay",
                slug="ledgerpay",
                category=Vendor.Category.FINANCE,
                criticality=Vendor.Criticality.CRITICAL,
                status=Vendor.Status.ACTIVE,
                description="Processes card payments, refunds, and settlement reporting.",
                owner=users["manager"],
                pii=True,
                production=False,
                finance=True,
                spend="780000.00",
                contract_expiry=today + timedelta(days=230),
                next_review=today + timedelta(days=305),
            ),
            "dataarc": self._vendor(
                organization,
                name="DataArc Analytics",
                slug="dataarc-analytics",
                category=Vendor.Category.DATA,
                criticality=Vendor.Criticality.HIGH,
                status=Vendor.Status.UNDER_REVIEW,
                description="Provides product analytics and customer-behaviour reporting.",
                owner=users["analyst"],
                pii=True,
                production=False,
                finance=False,
                spend="320000.00",
                contract_expiry=today + timedelta(days=72),
                next_review=today - timedelta(days=4),
            ),
            "counsel": self._vendor(
                organization,
                name="CounselWorks",
                slug="counselworks",
                category=Vendor.Category.PROFESSIONAL,
                criticality=Vendor.Criticality.MEDIUM,
                status=Vendor.Status.ONBOARDING,
                description="External legal counsel for commercial agreements and disputes.",
                owner=users["viewer"],
                pii=False,
                production=False,
                finance=False,
                spend="185000.00",
                contract_expiry=today + timedelta(days=300),
                next_review=today + timedelta(days=15),
            ),
        }

        nimbus = self._assessment(
            organization,
            vendors["nimbus"],
            title="Annual security and privacy review",
            scope="Production hosting, managed databases, support access, and backup resilience.",
            assessor=users["manager"],
            due_date=today - timedelta(days=18),
            status=Assessment.Status.COMPLETED,
            completed_at=now - timedelta(days=20),
            responses=["no", "partial", "yes", "partial", "no", "yes", "partial", "yes"],
        )
        ledger = self._assessment(
            organization,
            vendors["ledger"],
            title="Payment processor assurance review",
            scope="Payment data flow, access security, resilience, and PCI assurance.",
            assessor=users["manager"],
            due_date=today - timedelta(days=45),
            status=Assessment.Status.COMPLETED,
            completed_at=now - timedelta(days=50),
            responses=["yes", "yes", "yes", "partial", "yes", "yes", "yes", "yes"],
        )
        dataarc = self._assessment(
            organization,
            vendors["dataarc"],
            title="Renewal privacy and resilience review",
            scope="Analytics ingestion, retention, subprocessors, and service continuity.",
            assessor=users["analyst"],
            due_date=today - timedelta(days=1),
            status=Assessment.Status.IN_REVIEW,
            completed_at=None,
            responses=["yes", "partial", "yes", "no", "", "partial", "", "yes"],
        )

        findings = {
            "mfa": self._finding(
                organization,
                nimbus,
                title="Privileged support access lacks enforced MFA",
                description=(
                    "A legacy support workflow can access the management plane without MFA."
                ),
                severity=Finding.Severity.CRITICAL,
                owner=users["manager"],
                status=Finding.Status.OPEN,
                due_date=today - timedelta(days=5),
            ),
            "dr": self._finding(
                organization,
                nimbus,
                title="Disaster recovery evidence is out of date",
                description="The latest supplied recovery exercise report is over 18 months old.",
                severity=Finding.Severity.HIGH,
                owner=users["analyst"],
                status=Finding.Status.IN_PROGRESS,
                due_date=today + timedelta(days=12),
            ),
            "processor": self._finding(
                organization,
                ledger,
                title="Subprocessor inventory needed contract reference",
                description="The public inventory did not reference the current DPA revision.",
                severity=Finding.Severity.LOW,
                owner=users["manager"],
                status=Finding.Status.RESOLVED,
                due_date=today - timedelta(days=35),
                resolution_notes=(
                    "LedgerPay linked the current DPA and dated subprocessor register."
                ),
                resolved_at=now - timedelta(days=30),
            ),
            "retention": self._finding(
                organization,
                dataarc,
                title="Deletion verification is not independently evidenced",
                description="The retention policy is documented, but deletion jobs lack evidence.",
                severity=Finding.Severity.MEDIUM,
                owner=users["analyst"],
                status=Finding.Status.ACCEPTED,
                due_date=today + timedelta(days=45),
                resolution_notes="Risk accepted until the renewal control milestone.",
            ),
        }

        self._activity(
            organization,
            users["manager"],
            vendors["nimbus"],
            nimbus,
            "NimbusCloud annual assessment completed.",
            now - timedelta(days=20),
        )
        self._activity(
            organization,
            users["manager"],
            vendors["nimbus"],
            nimbus,
            f"Critical finding opened: {findings['mfa'].title}",
            now - timedelta(days=19),
        )
        self._activity(
            organization,
            users["manager"],
            vendors["ledger"],
            ledger,
            "LedgerPay assurance review completed with low residual risk.",
            now - timedelta(days=50),
        )
        self._activity(
            organization,
            users["analyst"],
            vendors["dataarc"],
            dataarc,
            "DataArc renewal review moved to evidence review.",
            now - timedelta(days=2),
        )
        self._activity(
            organization,
            users["analyst"],
            vendors["dataarc"],
            dataarc,
            f"Risk accepted: {findings['retention'].title}",
            now - timedelta(days=1),
        )

        self.stdout.write(self.style.SUCCESS("VendorSentry demo workspace is ready."))
        self.stdout.write("Password for every demo account: DemoPass123!")
        self.stdout.write("Users: demo_risk, demo_risk_manager, demo_analyst, demo_auditor")

    def _user(
        self,
        organization,
        *,
        username,
        first_name,
        last_name,
        email,
        role,
        team,
        title,
    ):
        user, _ = User.objects.update_or_create(
            username=username,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "is_active": True,
            },
        )
        user.set_password(self.password)
        user.save(update_fields=["password"])
        Membership.objects.update_or_create(
            user=user,
            defaults={
                "organization": organization,
                "role": role,
                "team": team,
                "title": title,
            },
        )
        return user

    def _vendor(
        self,
        organization,
        *,
        name,
        slug,
        category,
        criticality,
        status,
        description,
        owner,
        pii,
        production,
        finance,
        spend,
        contract_expiry,
        next_review,
    ):
        vendor, _ = Vendor.objects.update_or_create(
            organization=organization,
            slug=slug,
            defaults={
                "name": name,
                "category": category,
                "criticality": criticality,
                "status": status,
                "service_description": description,
                "business_owner": owner,
                "handles_personal_data": pii,
                "has_production_access": production,
                "has_financial_access": finance,
                "annual_spend": Decimal(spend),
                "contract_expiry": contract_expiry,
                "next_review": next_review,
            },
        )
        vendor.full_clean()
        vendor.save()
        return vendor

    def _assessment(
        self,
        organization,
        vendor,
        *,
        title,
        scope,
        assessor,
        due_date,
        status,
        completed_at,
        responses,
    ):
        assessment, _ = Assessment.objects.update_or_create(
            organization=organization,
            vendor=vendor,
            title=title,
            defaults={
                "scope": scope,
                "assessor": assessor,
                "due_date": due_date,
                "status": status,
                "completed_at": completed_at,
            },
        )
        assessment.full_clean()
        assessment.save()
        controls = create_baseline_controls(assessment)
        for control, response in zip(controls, responses, strict=True):
            control.response = response
            control.evidence = (
                f"https://example.com/evidence/{vendor.slug}/{control.sort_order}"
                if response
                else ""
            )
            control.notes = (
                "Evidence reviewed against the current assurance period."
                if response == AssessmentControl.Response.YES
                else "Follow-up evidence or remediation is required."
                if response
                else ""
            )
            control.full_clean()
            control.save(update_fields=["response", "evidence", "notes"])
        return assessment

    def _finding(
        self,
        organization,
        assessment,
        *,
        title,
        description,
        severity,
        owner,
        status,
        due_date,
        resolution_notes="",
        resolved_at=None,
    ):
        finding, _ = Finding.objects.update_or_create(
            organization=organization,
            assessment=assessment,
            title=title,
            defaults={
                "vendor": assessment.vendor,
                "description": description,
                "severity": severity,
                "owner": owner,
                "status": status,
                "due_date": due_date,
                "resolution_notes": resolution_notes,
                "resolved_at": resolved_at,
            },
        )
        finding.full_clean()
        finding.save()
        return finding

    def _activity(self, organization, actor, vendor, assessment, message, created_at):
        activity, _ = Activity.objects.update_or_create(
            organization=organization,
            vendor=vendor,
            assessment=assessment,
            message=message,
            defaults={"actor": actor},
        )
        activity.full_clean()
        activity.save()
        Activity.objects.filter(pk=activity.pk).update(created_at=created_at)
