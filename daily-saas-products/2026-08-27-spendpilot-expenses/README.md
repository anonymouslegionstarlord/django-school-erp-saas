# SpendPilot — Django Expense Management SaaS

SpendPilot is a portfolio-ready, multi-tenant expense reporting, approval, and reimbursement platform built with Python and Django. Employees submit itemized claims, policy exceptions are surfaced automatically, managers record approval decisions, and finance closes the loop with reimbursement tracking.

![Django](https://img.shields.io/badge/Django-5.2_LTS-0c4b33?logo=django)
![Python](https://img.shields.io/badge/Python-3.12-3776ab?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-ready-4169e1?logo=postgresql&logoColor=white)
![Coverage](https://img.shields.io/badge/test_coverage-91%25-315c43)

## Product capabilities

- Isolated company workspaces with owner, manager, employee, and finance roles
- Self-service company registration with starter categories and a cost center
- Draft, submitted, approved, rejected, and reimbursed report workflow
- Itemized expenses with merchant, date, category, amount, description, and receipt URL
- Configurable category limits and receipt thresholds
- Automatic flags for limit breaches, missing receipts, and out-of-trip dates
- Self-approval prevention and reason-required rejection
- Exception notes required before approving a report with policy flags
- Separate approval and reimbursement permissions
- Cost center and expense category administration
- Spend dashboard, review queue, reimbursement queue, and category analytics
- Append-only report activity history
- Role-aware and tenant-scoped JSON APIs
- Responsive server-rendered frontend
- Repeatable sample-data command
- SQLite for a zero-config first run and PostgreSQL for Docker/production
- Secure production defaults, WhiteNoise, Gunicorn, Docker, and Render configuration

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

### 2. Clone and enter SpendPilot

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-27-spendpilot-expenses
```

### 3. Create and activate a virtual environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If script execution is blocked, run this once in the same terminal and activate again:

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
cd django-school-erp-saas/daily-saas-products/2026-08-27-spendpilot-expenses
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
| Owner | `demo_spend` | View all spend, approve, reimburse, configure policy |
| Manager | `demo_manager` | Review other users' submitted reports |
| Employee | `demo_employee` | Create, edit, submit, and resubmit personal claims |
| Finance | `demo_finance` | Configure controls and record reimbursements |

The command is idempotent and resets these demo passwords. It is intended only for local or disposable demonstration databases.

## Run with Docker and PostgreSQL

Install Docker Desktop, enter this project directory, then run:

```bash
docker compose up --build
```

The container applies migrations, creates demo data, and starts Gunicorn. Open <http://localhost:8000>.

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

## Workflow and permissions

```text
Employee: Draft → Submitted ───────────────┐
                         Manager: Rejected ├→ employee edits/resubmits
                         Manager: Approved ┘
                                  ↓
                         Finance: Reimbursed
```

| Capability | Owner | Manager | Employee | Finance |
|---|:---:|:---:|:---:|:---:|
| View all workspace reports | Yes | Yes | No | Yes |
| Create and submit own report | Yes | Yes | Yes | Yes |
| Approve another user's report | Yes | Yes | No | No |
| Approve own report | No | No | No | No |
| Record reimbursement | Yes | No | No | Yes |
| Configure categories/cost centers | Yes | No | No | Yes |

Employees only see their own reports. Non-employee roles see all reports in their own workspace, never records from another tenant.

## Policy evaluation

SpendPilot evaluates every expense item when it is saved:

1. The amount is compared with the category's daily limit when that limit is non-zero.
2. A receipt URL is required above the configured receipt threshold when that threshold is non-zero.
3. If the report has trip dates, the expense date is checked against that window.

Policy flags are visible warnings rather than hard denials. This supports legitimate exceptions while preserving accountability: an approver must enter an exception note before approving a flagged report. Receipt URLs point to documents stored in an approved external system; file storage, malware scanning, and retention are deliberately not faked in this MVP.

## JSON API

Sign in through the web application first, then use:

| Endpoint | Purpose |
|---|---|
| `/api/summary/` | Role-aware workspace totals and report counts |
| `/api/reports/` | Visible reports; accepts `?status=submitted` |
| `/api/reports/<id>/` | One visible report and its itemized expenses |
| `/api/policy/` | Workspace categories, thresholds, and cost centers |

Example after signing in through a browser:

```bash
curl --cookie "sessionid=YOUR_SESSION_COOKIE" http://127.0.0.1:8000/api/reports/
```

All API querysets use the authenticated membership's organization and role. Cross-tenant IDs return `404` rather than revealing that a record exists. These endpoints are read-only in the MVP; browser forms own the audited state transitions.

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

Run these from the SpendPilot directory with the virtual environment active:

```bash
# Migrate and load sample data
python manage.py migrate
python manage.py seed_demo

# Create a production administrator
python manage.py createsuperuser

# Development and production configuration checks
python manage.py check
DJANGO_DEBUG=False DJANGO_SECRET_KEY=replace-this-with-a-long-test-value \
  DJANGO_ALLOWED_HOSTS=example.com python manage.py check --deploy

# Detect missing migrations
python manage.py makemigrations --check --dry-run

# Format, lint, and test
ruff format --check .
ruff check .
coverage run manage.py test
coverage report

# Production static assets
DJANGO_DEBUG=False DJANGO_SECRET_KEY=replace-this-with-a-long-test-value \
  DJANGO_ALLOWED_HOSTS=example.com python manage.py collectstatic --noinput
```

## Architecture

```text
2026-08-27-spendpilot-expenses/
├── config/                       # Settings, root URL routing, ASGI/WSGI
├── expenses/
│   ├── management/commands/seed_demo.py
│   ├── migrations/              # Versioned database schema
│   ├── static/expenses/app.css  # Responsive design system
│   ├── models.py                # Tenancy, policy, reports, items, audit log
│   ├── forms.py                 # Tenant-filtered forms and registration
│   ├── views.py                 # Role-aware web workflows and APIs
│   └── tests.py                 # Isolation, authorization, policy, API tests
├── templates/                   # Landing, auth, dashboard, reports, controls
├── Dockerfile
├── docker-compose.yml
└── render.yaml
```

The `Organization` is the tenant boundary. A user has one `Membership`, and every business record stores an organization foreign key. Views begin with the authenticated membership, relational form choices are filtered to that organization, object lookups include the tenant, and model validation rejects cross-tenant relationships. Role checks are performed on the server, not inferred from hidden navigation.

## Secure defaults

- CSRF middleware protects state-changing browser forms.
- Session and CSRF cookies become secure when debug is disabled.
- Production mode enables HTTPS redirect, HSTS, proxy SSL handling, content-type sniffing protection, and clickjacking denial.
- Passwords are handled by Django's hashing and validator stack.
- State changes use POST and explicit authorization checks.
- Self-approval is blocked independently of the user interface.
- `.env`, SQLite databases, virtual environments, coverage files, caches, collected static assets, and media are ignored.
- The local fallback secret is deliberately marked insecure and must be replaced in production.

## Deploy to Render

The included `render.yaml` is a reference blueprint. For this monorepo, create a Render web service from the GitHub repository and set **Root Directory** to:

```text
daily-saas-products/2026-08-27-spendpilot-expenses
```

Then configure:

```text
Build command: pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
Start command: gunicorn config.wsgi:application
```

Attach a managed PostgreSQL database as `DATABASE_URL`, generate a long `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=False`, and set the exact deployment host/origin in `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`. Do not run `seed_demo` against a real production database.

Before launching, run the tests and deployment check locally, review account provisioning, add rate limiting and observability at the platform edge, and replace receipt URLs with an approved storage integration if the product will handle real financial documents.

## License

This project inherits the repository's MIT License.
