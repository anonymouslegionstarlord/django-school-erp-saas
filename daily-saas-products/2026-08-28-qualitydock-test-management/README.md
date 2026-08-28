# QualityDock — Django QA Test Management SaaS

QualityDock is a portfolio-ready, multi-tenant quality-assurance workspace built with Python and Django. QA teams maintain reusable test cases, assemble versioned test runs, assign executions, capture evidence and defects, and read release-readiness metrics from one responsive application.

![Django](https://img.shields.io/badge/Django-5.2_LTS-0c4b33?logo=django)
![Python](https://img.shields.io/badge/Python-3.12-3776ab?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-ready-4169e1?logo=postgresql&logoColor=white)
![Coverage](https://img.shields.io/badge/test_coverage-91%25-315c43)

## Product capabilities

- Isolated QA workspaces with owner, QA lead, tester, and viewer roles
- Self-service organization registration with a starter product and test suite
- Product and suite catalog for web, mobile, API, or internal applications
- Reusable test cases with priorities, test types, requirements, preconditions, steps, and expected results
- Planned, in-progress, and completed test-run lifecycle
- Version, environment, schedule, scope, and assignee tracking
- Pass, fail, blocked, skipped, and not-run execution results
- Failure evidence rules: failed cases require an actual result and defect reference
- Tester assignment enforcement and read-only completed runs
- Run completion gate that prevents unresolved not-run executions
- Live completion rate, pass rate, critical failure, and blocker metrics
- Searchable case library and filterable execution board
- Append-only run activity timeline and team comments
- Tenant-scoped JSON APIs for dashboards and integrations
- Responsive, server-rendered frontend with no JavaScript build step
- Idempotent realistic sample data
- SQLite for a zero-config first run and PostgreSQL for Docker/production
- Secure production settings, WhiteNoise, Gunicorn, Docker, Render, and GitHub Actions support

## Technology

| Layer | Choice |
|---|---|
| Backend | Python 3.12, Django 5.2 LTS |
| Frontend | Django templates and custom responsive CSS |
| Authentication | Django sessions and password validators |
| API | Authenticated, read-only Django JSON views |
| Database | SQLite locally; PostgreSQL in Docker and production |
| Production | Gunicorn and WhiteNoise |
| Quality | Django TestCase, Coverage, Ruff, GitHub Actions |

## First-time setup — Windows

These commands use PowerShell on Windows 10 or 11.

### 1. Install prerequisites

Install [Python 3.12](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win). During Python installation, select **Add Python to PATH**.

### 2. Clone and enter QualityDock

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-28-qualitydock-test-management
```

### 3. Create and activate a virtual environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this once in the same terminal and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 4. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 5. Configure and initialize

```powershell
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
```

The local defaults work without editing `.env`. Never use its example secret in production.

### 6. Run

```powershell
python manage.py runserver
```

Open <http://127.0.0.1:8000>.

## First-time setup — macOS or Linux

Install Python 3.12 and Git, then run:

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-08-28-qualitydock-test-management
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open <http://127.0.0.1:8000>.

If `python3.12` is unavailable but `python3 --version` reports 3.12 or newer, use `python3` in the virtual-environment command.

## Demo accounts

Run `python manage.py seed_demo`. All four accounts use `DemoPass123!`:

| Role | Username | Useful workflow |
|---|---|---|
| Owner | `demo_quality` | View release health and manage every QA artifact |
| QA lead | `demo_qa_lead` | Build cases and runs, assign work, start and complete runs |
| Tester | `demo_tester` | Execute assigned cases, attach evidence, and comment |
| Viewer | `demo_viewer` | Review dashboards, cases, runs, and API data without mutations |

The command is idempotent and resets these demo passwords. It is intended only for local or disposable demonstration databases.

## Run with Docker and PostgreSQL

Install Docker Desktop, enter this project directory, then run:

```bash
docker compose up --build
```

The web container waits for PostgreSQL, applies migrations, creates demo data, and starts Gunicorn. Open <http://localhost:8000>.

Useful Docker commands:

```bash
# Follow application logs
docker compose logs -f web

# Run Django checks
docker compose exec web python manage.py check

# Open a Django shell
docker compose exec web python manage.py shell

# Stop while preserving PostgreSQL data
docker compose down

# Stop and delete the local PostgreSQL volume
docker compose down -v
```

## QA workflow and permissions

```text
QA lead: define product → suite → ready test cases
                                  ↓
QA lead: create planned run → add ready cases → assign testers
                                  ↓
Tester: not run → passed / failed / blocked / skipped
                                  ↓
QA lead: resolve every not-run case → complete and freeze run
```

| Capability | Owner | QA lead | Tester | Viewer |
|---|:---:|:---:|:---:|:---:|
| View workspace quality data | Yes | Yes | Yes | Yes |
| Manage products, suites, and cases | Yes | Yes | No | No |
| Create, scope, start, and complete runs | Yes | Yes | No | No |
| Update any execution in an open run | Yes | Yes | No | No |
| Update an assigned execution | Yes | Yes | Yes | No |
| Comment on an open or completed run | Yes | Yes | Yes | No |
| Change a completed run | No | No | No | No |

Every role is limited to its own organization. A tester cannot update an unassigned case or another tester's assignment. Owners and QA leads can coordinate the whole run. Completed runs remain visible but execution results are immutable.

## Release-readiness rules

QualityDock treats evidence and workflow gates as backend rules rather than presentation hints:

1. A test run can contain only cases from its selected product and organization.
2. Only cases marked **Ready** are added to a run's executable scope.
3. Saving the first result automatically starts a planned run and records its start date.
4. A failed result requires both an actual result and a defect reference.
5. A blocked result requires an actual result explaining the blocker.
6. A run cannot be completed while any execution is still **Not run**.
7. A completed run is read-only and records its final pass rate in the activity timeline.

`completion_rate` is the percentage of scoped cases no longer marked **Not run**. `pass_rate` is passed cases divided by all executed cases, so failures, blockers, and skips remain visible in the release signal.

## JSON API

Sign in through the web application first, then use:

| Endpoint | Purpose |
|---|---|
| `/api/summary/` | Workspace totals, active runs, pass rate, and critical failures |
| `/api/products/` | Product catalog with case and run counts |
| `/api/cases/` | Test case library; accepts `?product=<id>` |
| `/api/runs/` | Test runs and metrics; accepts `?status=planned` |
| `/api/runs/<id>/` | One run with tenant-scoped execution results |

Example after signing in through a browser:

```bash
curl --cookie "sessionid=YOUR_SESSION_COOKIE" http://127.0.0.1:8000/api/runs/
```

All API querysets start from the authenticated membership's organization. Cross-tenant IDs return `404` rather than confirming that another workspace's record exists. These endpoints are intentionally read-only in the MVP; the browser workflows own validated state transitions and activity logging.

## Environment variables

| Variable | Production | Purpose |
|---|:---:|---|
| `DJANGO_SECRET_KEY` | Required | Long, unique random signing secret |
| `DJANGO_DEBUG` | Required | Set to `False` |
| `DJANGO_ALLOWED_HOSTS` | Required | Comma-separated deployment hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Required for HTTPS forms | Comma-separated origins including `https://` |
| `DATABASE_URL` | Recommended | PostgreSQL connection URL |
| `DJANGO_TIME_ZONE` | Optional | Defaults to `Asia/Kolkata` |
| `DJANGO_SECURE_SSL_REDIRECT` | Optional | Defaults to `True` when debug is off |

When `DATABASE_URL` is unset, the project uses a local `db.sqlite3`, which is ignored by Git.

## Common commands

Run these from the QualityDock directory with the virtual environment active:

```bash
# Migrate and load or refresh sample data
python manage.py migrate
python manage.py seed_demo

# Create a production administrator
python manage.py createsuperuser

# Development and production configuration checks
python manage.py check
DJANGO_DEBUG=False DJANGO_SECRET_KEY=replace-this-with-a-long-unique-test-secret-value \
  DJANGO_ALLOWED_HOSTS=example.com \
  DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com \
  python manage.py check --deploy

# Detect missing migrations
python manage.py makemigrations --check --dry-run

# Format, lint, and test
ruff format --check .
ruff check .
coverage run manage.py test
coverage report --fail-under=85

# Production static assets
DJANGO_DEBUG=False DJANGO_SECRET_KEY=replace-this-with-a-long-unique-test-secret-value \
  DJANGO_ALLOWED_HOSTS=example.com python manage.py collectstatic --noinput
```

## Architecture

```text
2026-08-28-qualitydock-test-management/
├── config/                  # Settings, root URL routing, ASGI/WSGI
├── qa/
│   ├── management/commands/seed_demo.py
│   ├── migrations/         # Versioned database schema
│   ├── static/qa/app.css   # Responsive design system
│   ├── models.py           # Tenancy, cases, runs, results, activity
│   ├── forms.py            # Tenant-filtered forms and evidence rules
│   ├── views.py            # Role-aware workflows and JSON APIs
│   └── tests.py            # Isolation, authorization, lifecycle, API tests
├── templates/              # Landing, auth, dashboard, cases, runs
├── Dockerfile
├── docker-compose.yml
└── render.yaml
```

`Organization` is the tenant boundary. A Django user has one `Membership`, and every business model carries an organization foreign key. Views resolve the authenticated membership first, relational form choices are restricted to that organization, object lookups include the tenant, and model validation rejects cross-organization relationships. Permissions are checked by the server for every mutation; hiding a button is never the authorization mechanism.

Test cases are reusable specifications grouped by product and suite. A `TestExecution` is the run-specific snapshot of assignment, result, evidence, and defect linkage. A uniqueness constraint prevents one case appearing twice in a run, and an `Activity` record creates a compact append-only run history.

## Secure defaults

- CSRF middleware protects state-changing browser forms.
- Session and CSRF cookies become secure when debug is disabled.
- Production mode enables HTTPS redirect, HSTS, proxy SSL handling, content-type sniffing protection, and clickjacking denial.
- Passwords use Django's hashing and validator stack.
- State transitions require POST plus explicit role and tenant checks.
- Cross-tenant foreign keys are filtered in forms and rejected by model validation.
- Failed execution evidence and completion gates are validated server-side.
- `.env`, SQLite databases, virtual environments, coverage files, caches, collected static assets, and media are ignored.
- The local fallback secret is deliberately marked insecure and must be replaced in production.

For real production use, add SSO or invitation-based provisioning, API tokens and rate limiting, object storage with malware scanning for evidence files, immutable audit export, background notifications, database backups, observability, and an integration with the team's defect tracker.

## Deploy to Render

The included `render.yaml` is a reference blueprint. For this monorepo, create a Render web service from the GitHub repository and set **Root Directory** to:

```text
daily-saas-products/2026-08-28-qualitydock-test-management
```

Then configure:

```text
Build command: pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
Start command: gunicorn config.wsgi:application
```

Attach a managed PostgreSQL database as `DATABASE_URL`, generate a long `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=False`, and set the exact deployment host/origin in `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`. Do not run `seed_demo` against a real production database.

Before launch, run the complete test suite and deployment check, review account provisioning, enable platform-edge rate limiting, add monitoring and backups, and connect evidence and defect references to approved systems.

## License

This project inherits the repository's MIT License.
