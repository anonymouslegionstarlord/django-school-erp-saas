# VendorSentry — Django Third-Party Risk SaaS

VendorSentry is a portfolio-ready, multi-tenant vendor risk and remediation platform built with Python and Django. Risk teams map third-party exposure, run weighted control assessments, calculate residual risk, assign findings, track deadlines, and preserve an evidence trail from one responsive workspace.

![Django](https://img.shields.io/badge/Django-5.2_LTS-0c4b33?logo=django)
![Python](https://img.shields.io/badge/Python-3.12-3776ab?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-ready-4169e1?logo=postgresql&logoColor=white)
![Coverage](https://img.shields.io/badge/test_coverage-98%25-6857d9)

## Product capabilities

- Isolated organization workspaces with owner, risk manager, analyst, and viewer roles
- Self-service registration with an editable starter vendor
- Vendor register with category, criticality, lifecycle, owner, annual spend, and contract dates
- Personal-data, production, and financial-access exposure mapping
- Eight-control baseline across security, privacy, resilience, compliance, and governance
- Weighted implemented, partial, missing, and not-applicable responses
- Normalized residual-risk scores with low, moderate, high, and critical ratings
- Draft, in-review, and completed assessment workflow
- Completion gate requiring every control to be answered
- Evidence URLs and contextual notes for every control
- Immutable completed control reviews and automatic annual review scheduling
- Findings with severity, ownership, due dates, risk acceptance, resolution notes, and overdue detection
- Tenant-safe audit activity across vendor, assessment, and remediation events
- Portfolio metrics for spend, critical attention, reviews due, open findings, and average risk
- Searchable and filterable vendor and assessment views
- Authenticated tenant-scoped JSON APIs for reporting and integrations
- Responsive server-rendered frontend with no JavaScript build step
- Repeatable realistic demonstration data
- SQLite locally and PostgreSQL for Docker or production
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

### 2. Clone and enter VendorSentry

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-31-vendorsentry-vendor-risk
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

The safe local defaults work without editing `.env`. Never use its example secret in production.

### 6. Start the server

```powershell
python manage.py runserver
```

Open <http://127.0.0.1:8000>.

## First-time setup — macOS or Linux

Install Python 3.12 and Git, then run:

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-08-31-vendorsentry-vendor-risk
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open <http://127.0.0.1:8000>. If `python3.12` is unavailable but `python3 --version` reports 3.12 or newer, use `python3` to create the environment.

## Demo accounts

Run `python manage.py seed_demo`. All accounts use `DemoPass123!`:

| Role | Username | Useful workflow |
|---|---|---|
| Owner | `demo_risk` | Review portfolio posture and manage every workflow |
| Risk manager | `demo_risk_manager` | Manage vendors, assess controls, and oversee remediation |
| Risk analyst | `demo_analyst` | Perform assigned reviews, link evidence, and own findings |
| Viewer | `demo_auditor` | Inspect the portfolio, completed reviews, and reporting APIs |

The command is idempotent and resets these passwords. It is intended only for local or disposable demonstration databases. Never run it against a real production database.

The sample workspace contains:

- Four vendors across cloud, payments, analytics, and professional services
- Critical, high, and medium business criticality
- Two completed assessments and one overdue review in progress
- Implemented, partial, missing, and unanswered control evidence
- Critical, high, medium, and low remediation findings
- Open, in-progress, accepted, and resolved outcomes
- A chronological audit activity feed

## Risk methodology

Every new assessment receives eight baseline controls. Each control has a weight from one to five.

| Response | Risk points |
|---|---:|
| Implemented | `0 × weight` |
| Partially implemented | `10 × weight` |
| Not implemented | `20 × weight` |
| Not applicable | Excluded from the denominator |

The score is normalized to 100 using answered, applicable controls:

```text
residual risk = earned risk points / maximum applicable points × 100
```

| Score | Rating |
|---:|---|
| 0–24 | Low |
| 25–49 | Moderate |
| 50–74 | High |
| 75–100 | Critical |

Draft and in-review scores are directional because unanswered controls are excluded. Completion requires every control to have a response, freezes control editing, sets the vendor active, and schedules the next review for one year later.

## Role permissions

| Capability | Owner | Risk manager | Analyst | Viewer |
|---|:---:|:---:|:---:|:---:|
| View tenant data and APIs | ✓ | ✓ | ✓ | ✓ |
| Add or edit vendors | ✓ | ✓ | — | — |
| Create assessments and findings | ✓ | ✓ | ✓ | — |
| Score an assessment | ✓ | ✓ | When assigned | — |
| Complete an assessment | ✓ | ✓ | When assigned | — |
| Update a finding | ✓ | ✓ | When assigned as owner | — |

Every queryset is scoped to the signed-in membership. Forms constrain foreign-key choices, and model validation rejects mismatched organization, vendor, assessment, user, and owner relationships.

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

# Stop without deleting PostgreSQL data
docker compose down
```

Run `docker compose down -v` only when you intentionally want to remove the local database volume.

## Environment variables

| Variable | Required in production | Purpose |
|---|:---:|---|
| `DJANGO_SECRET_KEY` | Yes | Long random application secret |
| `DJANGO_DEBUG` | Yes | Set to `False` in production |
| `DJANGO_ALLOWED_HOSTS` | Yes | Comma-separated deployment hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | For HTTPS forms | Origins including the `https://` scheme |
| `DATABASE_URL` | Recommended | PostgreSQL URL; SQLite is the local fallback |
| `DJANGO_TIME_ZONE` | No | Defaults to `Asia/Kolkata` |
| `DJANGO_SECURE_SSL_REDIRECT` | No | Defaults to `True` when debug is disabled |

Production mode enables secure cookies, HSTS, proxy HTTPS handling, MIME sniffing protection, frame denial, and WhiteNoise manifest storage.

## JSON API

Sign in through the browser and use these read-only endpoints in the same authenticated session:

| Endpoint | Purpose | Filters |
|---|---|---|
| `/api/summary/` | Portfolio, review, risk, and remediation metrics | — |
| `/api/vendors/` | Vendor criticality, exposure, spend, and review state | — |
| `/api/assessments/` | Coverage, score, rating, assessor, and due state | `status` |
| `/api/findings/` | Finding severity, owner, deadline, and status | `status`, `severity` |

For example, after signing in, open <http://127.0.0.1:8000/api/summary/>. API clients cannot supply an organization identifier; the workspace always comes from the authenticated membership.

## Common development commands

```bash
# Configuration and migration checks
python manage.py check
python manage.py makemigrations --check --dry-run

# Tests and coverage gate
coverage run manage.py test
coverage report --fail-under=88

# Format and lint
ruff format .
ruff check .

# Refresh demonstration data
python manage.py seed_demo

# Create a real administrator
python manage.py createsuperuser

# Build production static assets
python manage.py collectstatic --noinput
```

## Architecture

```text
Organization
├── Membership ── User + role
├── Vendor
│   ├── Assessment
│   │   ├── AssessmentControl
│   │   └── Finding
│   └── Activity
└── tenant-scoped JSON reporting
```

`Membership` binds a Django user to one `Organization` and supplies role permissions. The `workspace_required` decorator resolves it for authenticated pages and APIs. Every write validates ownership again at the model boundary. Assessment creation and completion use transactions because they update controls, vendor lifecycle, scheduling, and audit events together.

For a larger production deployment, add invitations and SSO, custom control libraries, file evidence storage, comments and approvals, notification jobs, API tokens, immutable audit exports, rate limiting, and PostgreSQL row-level security.

## Project structure

```text
2026-08-31-vendorsentry-vendor-risk/
├── config/                         # Settings, root URLs, WSGI and ASGI
├── risk/                           # Tenant models, forms, views, APIs and tests
│   ├── management/commands/seed_demo.py
│   ├── migrations/
│   └── static/risk/app.css
├── templates/                      # Responsive public and authenticated UI
├── Dockerfile
├── docker-compose.yml
├── render.yaml
├── requirements.txt
├── requirements-dev.txt
└── manage.py
```

## Deploy to Render

The included `render.yaml` defines a Django web service and PostgreSQL database.

1. Fork or push this repository to your GitHub account.
2. In Render, create a **Blueprint** from the repository.
3. Set the Blueprint root directory to `daily-saas-products/2026-08-31-vendorsentry-vendor-risk`.
4. Review the generated web service and database, then deploy.
5. Run `python manage.py createsuperuser` in the Render shell after deployment.
6. Do not seed demo credentials into a real customer environment.

The blueprint generates the secret key, disables debug mode, configures HTTPS origins, installs dependencies, collects static files, runs migrations, and starts Gunicorn. If you rename the service, update `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to match its final hostname.

## License

This product uses the repository's MIT license.
