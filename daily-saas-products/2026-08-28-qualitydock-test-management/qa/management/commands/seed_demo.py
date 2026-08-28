from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from qa.models import (
    Activity,
    Membership,
    Organization,
    Product,
    TestCase,
    TestExecution,
    TestRun,
    TestSuite,
)


class Command(BaseCommand):
    help = "Create or refresh the local QualityDock demonstration workspace."

    @transaction.atomic
    def handle(self, *args, **options):
        organization, _ = Organization.objects.update_or_create(
            slug="northstar-quality",
            defaults={"name": "Northstar Quality Engineering"},
        )
        users = {}
        user_specs = [
            ("demo_quality", "Mayank", "Dubey", Membership.Role.OWNER),
            ("demo_qa_lead", "Asha", "Mehta", Membership.Role.LEAD),
            ("demo_tester", "Rohan", "Kapoor", Membership.Role.TESTER),
            ("demo_viewer", "Neha", "Singh", Membership.Role.VIEWER),
        ]
        for username, first_name, last_name, role in user_specs:
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_staff": role == Membership.Role.OWNER,
                },
            )
            user.set_password("DemoPass123!")
            user.save(update_fields=["password"])
            Membership.objects.update_or_create(
                user=user,
                defaults={"organization": organization, "role": role},
            )
            users[role] = user

        products = {}
        for key, name, description, owner_role in [
            (
                "WEB",
                "Web Commerce",
                "Customer storefront, checkout, payment, and order journeys.",
                Membership.Role.LEAD,
            ),
            (
                "MOB",
                "Shopper Mobile",
                "iOS and Android shopping experience and notifications.",
                Membership.Role.OWNER,
            ),
        ]:
            product, _ = Product.objects.update_or_create(
                organization=organization,
                key=key,
                defaults={
                    "name": name,
                    "description": description,
                    "owner": users[owner_role],
                    "status": Product.Status.ACTIVE,
                },
            )
            products[key] = product

        suites = {}
        for product_key, name, description in [
            ("WEB", "Authentication", "Login, session, and account access."),
            ("WEB", "Checkout", "Cart-to-payment purchase journeys."),
            ("WEB", "Orders", "Order creation and post-purchase communication."),
            ("MOB", "Mobile smoke", "Critical launch and navigation confidence."),
        ]:
            suite, _ = TestSuite.objects.update_or_create(
                organization=organization,
                product=products[product_key],
                name=name,
                defaults={"description": description},
            )
            suites[(product_key, name)] = suite

        case_specs = [
            (
                "WEB-001",
                "WEB",
                "Authentication",
                "Valid customer can sign in",
                "AUTH-101",
                TestCase.Priority.CRITICAL,
                TestCase.TestType.SMOKE,
                "A verified customer account exists.\nThe user is signed out.",
                "1. Open the sign-in page.\n2. Enter valid credentials.\n3. Submit the form.",
                "The account dashboard opens and a secure session is created.",
            ),
            (
                "WEB-002",
                "WEB",
                "Authentication",
                "Invalid password does not disclose account state",
                "AUTH-108",
                TestCase.Priority.HIGH,
                TestCase.TestType.REGRESSION,
                "A customer account exists.",
                "1. Enter the registered email.\n2. Enter an invalid password.\n3. Submit.",
                "A generic authentication error appears and no session is created.",
            ),
            (
                "WEB-010",
                "WEB",
                "Checkout",
                "Guest completes checkout with UPI",
                "CHK-220",
                TestCase.Priority.CRITICAL,
                TestCase.TestType.FUNCTIONAL,
                "A sellable product is in stock and the payment sandbox is available.",
                (
                    "1. Add a product to cart.\n2. Continue as guest.\n"
                    "3. Enter delivery details.\n4. Select UPI.\n5. Approve payment."
                ),
                "One paid order is created and the confirmation page shows its reference.",
            ),
            (
                "WEB-011",
                "WEB",
                "Checkout",
                "Coupon survives a payment retry",
                "CHK-231",
                TestCase.Priority.CRITICAL,
                TestCase.TestType.INTEGRATION,
                "A valid coupon exists and the payment sandbox can simulate a decline.",
                (
                    "1. Apply the coupon.\n2. Submit a declined payment.\n"
                    "3. Retry with a successful method."
                ),
                "The discount remains applied and exactly one paid order is created.",
            ),
            (
                "WEB-020",
                "WEB",
                "Orders",
                "Order confirmation email follows capture",
                "ORD-310",
                TestCase.Priority.HIGH,
                TestCase.TestType.INTEGRATION,
                "Email sandbox access is available.",
                (
                    "1. Complete payment.\n2. Wait for order processing.\n"
                    "3. Inspect the customer inbox."
                ),
                "One confirmation email contains the correct items, totals, and order link.",
            ),
            (
                "WEB-030",
                "WEB",
                "Checkout",
                "Expired coupon is rejected clearly",
                "CHK-242",
                TestCase.Priority.MEDIUM,
                TestCase.TestType.REGRESSION,
                "An expired coupon code is available.",
                "1. Add an item to cart.\n2. Enter the expired coupon.\n3. Apply it.",
                "The total is unchanged and a clear expiry message is displayed.",
            ),
            (
                "MOB-001",
                "MOB",
                "Mobile smoke",
                "Application launches to the home feed",
                "MOB-010",
                TestCase.Priority.CRITICAL,
                TestCase.TestType.SMOKE,
                "The release build is installed on a supported device.",
                "1. Force close the app.\n2. Launch it from the device home screen.",
                "The branded launch screen transitions to a populated home feed without error.",
            ),
            (
                "MOB-002",
                "MOB",
                "Mobile smoke",
                "Deep link opens product details",
                "MOB-021",
                TestCase.Priority.HIGH,
                TestCase.TestType.SMOKE,
                "The application is installed and a product deep link is available.",
                "1. Open the product link from a message.\n2. Observe the destination.",
                "The matching product page opens with current price and availability.",
            ),
        ]
        cases = {}
        for (
            case_key,
            product_key,
            suite_name,
            title,
            requirement,
            priority,
            test_type,
            preconditions,
            steps,
            expected,
        ) in case_specs:
            test_case, _ = TestCase.objects.update_or_create(
                organization=organization,
                case_key=case_key,
                defaults={
                    "suite": suites[(product_key, suite_name)],
                    "title": title,
                    "requirement_reference": requirement,
                    "priority": priority,
                    "test_type": test_type,
                    "status": TestCase.Status.READY,
                    "preconditions": preconditions,
                    "steps": steps,
                    "expected_result": expected,
                    "created_by": users[Membership.Role.LEAD],
                },
            )
            cases[case_key] = test_case

        today = timezone.localdate()
        now = timezone.now()
        run_specs = [
            {
                "name": "Release 4.8 regression",
                "product": products["WEB"],
                "version": "4.8.0",
                "environment": TestRun.Environment.STAGING,
                "status": TestRun.Status.IN_PROGRESS,
                "start": today - timedelta(days=2),
                "due": today + timedelta(days=1),
                "executions": [
                    (
                        "WEB-001",
                        Membership.Role.TESTER,
                        TestExecution.Status.PASSED,
                        "Signed in and redirected correctly.",
                        "",
                        "",
                    ),
                    (
                        "WEB-002",
                        Membership.Role.TESTER,
                        TestExecution.Status.PASSED,
                        "Generic error shown; no session cookie issued.",
                        "",
                        "",
                    ),
                    (
                        "WEB-010",
                        Membership.Role.TESTER,
                        TestExecution.Status.PASSED,
                        "UPI sandbox created one paid order.",
                        "",
                        "https://example.com/evidence/web-010",
                    ),
                    (
                        "WEB-011",
                        Membership.Role.TESTER,
                        TestExecution.Status.FAILED,
                        "Coupon was removed after the first payment decline.",
                        "https://example.com/defects/QD-184",
                        "https://example.com/evidence/web-011",
                    ),
                    (
                        "WEB-020",
                        Membership.Role.LEAD,
                        TestExecution.Status.BLOCKED,
                        "Email sandbox is unavailable in staging.",
                        "",
                        "",
                    ),
                    ("WEB-030", Membership.Role.TESTER, TestExecution.Status.NOT_RUN, "", "", ""),
                ],
            },
            {
                "name": "Mobile 2.3 smoke",
                "product": products["MOB"],
                "version": "2.3.0",
                "environment": TestRun.Environment.QA,
                "status": TestRun.Status.COMPLETED,
                "start": today - timedelta(days=6),
                "due": today - timedelta(days=5),
                "completed_at": now - timedelta(days=5),
                "executions": [
                    (
                        "MOB-001",
                        Membership.Role.TESTER,
                        TestExecution.Status.PASSED,
                        "Launch and feed load passed on Android and iOS.",
                        "",
                        "https://example.com/evidence/mob-001",
                    ),
                    (
                        "MOB-002",
                        Membership.Role.TESTER,
                        TestExecution.Status.PASSED,
                        "Deep link opened the correct product on both platforms.",
                        "",
                        "",
                    ),
                ],
            },
            {
                "name": "Checkout hotfix verification",
                "product": products["WEB"],
                "version": "4.8.1-hotfix",
                "environment": TestRun.Environment.STAGING,
                "status": TestRun.Status.PLANNED,
                "start": today,
                "due": today + timedelta(days=1),
                "executions": [
                    ("WEB-010", Membership.Role.TESTER, TestExecution.Status.NOT_RUN, "", "", ""),
                    ("WEB-011", Membership.Role.TESTER, TestExecution.Status.NOT_RUN, "", "", ""),
                ],
            },
        ]
        for spec in run_specs:
            executions = spec["executions"]
            run, _ = TestRun.objects.update_or_create(
                organization=organization,
                name=spec["name"],
                defaults={
                    "product": spec["product"],
                    "target_version": spec["version"],
                    "environment": spec["environment"],
                    "status": spec["status"],
                    "start_date": spec["start"],
                    "due_date": spec["due"],
                    "created_by": users[Membership.Role.LEAD],
                    "completed_at": spec.get("completed_at"),
                },
            )
            run.executions.all().delete()
            run.activities.all().delete()
            for case_key, assignee_role, status, actual, defect, evidence in executions:
                execution = TestExecution(
                    organization=organization,
                    run=run,
                    test_case=cases[case_key],
                    assigned_to=users[assignee_role],
                    status=status,
                    actual_result=actual,
                    defect_reference=defect,
                    evidence_url=evidence,
                )
                execution.full_clean()
                execution.save()
            Activity.objects.create(
                organization=organization,
                run=run,
                actor=users[Membership.Role.LEAD],
                message=f"Demo run prepared for {run.target_version}",
            )
            if run.status != TestRun.Status.PLANNED:
                Activity.objects.create(
                    organization=organization,
                    run=run,
                    actor=users[Membership.Role.TESTER],
                    message=f"Execution progress: {run.executed_count}/{run.total_count} resolved",
                )
            if run.status == TestRun.Status.COMPLETED:
                Activity.objects.create(
                    organization=organization,
                    run=run,
                    actor=users[Membership.Role.LEAD],
                    message=f"Run completed at {run.pass_rate}% pass rate",
                )

        self.stdout.write(
            self.style.SUCCESS(
                "QualityDock demo ready: demo_quality / demo_qa_lead / demo_tester / "
                "demo_viewer (password: DemoPass123!)"
            )
        )
