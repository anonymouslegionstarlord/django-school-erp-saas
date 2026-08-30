# OpsBeacon — Django Incident Response SaaS

OpsBeacon is a portfolio-ready, multi-tenant incident response and service reliability platform built with Python and Django. Operations teams declare incidents, coordinate responders, publish trusted customer updates, measure resolution targets, and track follow-up work from one responsive command center.

![Django](https://img.shields.io/badge/Django-5.2_LTS-0c4b33?logo=django)
![Python](https://img.shields.io/badge/Python-3.12-3776ab?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-ready-4169e1?logo=postgresql&logoColor=white)
![Coverage](https://img.shields.io/badge/test_coverage-99%25-19b6a5)

## Product capabilities

- Isolated organization workspaces with owner, incident commander, responder, and viewer roles
- Self-service workspace registration with a starter service and secure Django authentication
- Service catalog with ownership, operational state, maintenance mode, and public visibility
- SEV-1 through SEV-4 incident declaration with configurable response context
- Guarded investigating, identified, monitoring, and resolved workflow
- Automatic service health derived from the most severe active incident
- Incident commander and responder assignment with explicit responsibilities
- Chronological internal and public incident updates
- Customer-safe public status page that never exposes internal timeline notes
- Severity-based resolution clocks, SLA-breach indicators, 30-day MTTR, and reliability metrics
- Follow-up action items with ownership, due dates, overdue detection, completion, and reopening
- Immutable resolved incidents and mandatory resolution summaries
- Searchable and filterable incident history and service catalog
- Tenant-scoped JSON APIs for reporting and integrations
- Polished responsive frontend with no JavaScript build step
- Repeatable realistic sample data with active, breached, and resolved incidents
- SQLite for a zero-configuration first run and PostgreSQL for Docker or production
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

### 2. Clone and enter OpsBeacon

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-30-opsbeacon-incident-management
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

Open <http://127.0.0.1:8000>. The public demonstration status page is at <http://127.0.0.1:8000/status/northstar-digital/>.

## First-time setup — macOS or Linux

Install Python 3.12 and Git, then run:

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-08-30-opsbeacon-incident-management
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open <http://127.0.0.1:8000>. If `python3.12` is unavailable but `python3 --version` reports 3.12 or newer, use `python3` to create the virtual environment.

## Demo accounts

Run `python manage.py seed_demo`. All four accounts use `DemoPass123!`:

| Role | Username | Useful workflow |
|---|---|---|
| Owner | `demo_ops` | View reliability metrics, manage services, and coordinate any incident |
| Incident commander | `demo_commander` | Declare incidents, control transitions, assign responders, and publish updates |
| Responder | `demo_responder` | Declare incidents, add timeline updates, and own action items |
| Viewer | `demo_observer` | Review operational history and authenticated reporting APIs |

The command is idempotent and resets these passwords. It is intended only for local or disposable demonstration databases. Never run it against a real production database.

The sample workspace contains four services, two active incidents, one recent resolved incident, public and internal updates, assigned response teams, and open, overdue, and completed action items.

## Incident response model

### Severity targets

| Severity | Intended impact | Resolution target |
|---|---|---:|
| SEV-1 | Critical, widespread customer impact | 60 minutes |
| SEV-2 | High-impact partial outage | 240 minutes |
| SEV-3 | Degraded experience or limited impact | 480 minutes |
| SEV-4 | Low-impact operational issue | 1,440 minutes |

OpsBeacon displays elapsed time, flags active breaches, and calculates 30-day mean time to resolution from resolved incidents.

### State transitions

```text
Investigating ──> Identified ──> Monitoring ──> Resolved
       │               └──────────────────────────> │
       ├────────────────> Monitoring ──> Investigating
       └────────────────────────────────> Resolved
```

Resolving requires a substantive resolution summary. Resolved incidents become read-only to preserve their history. A status update may remain internal or be explicitly published; the public page selects only updates marked public.

### Role permissions

| Capability | Owner | Commander | Responder | Viewer |
|---|:---:|:---:|:---:|:---:|
| View workspace and APIs | ✓ | ✓ | ✓ | ✓ |
| Manage service catalog | ✓ | ✓ | — | — |
| Declare and update incidents | ✓ | ✓ | ✓ | — |
| Assign responders | ✓ | ✓ | Incident commander only | — |
| Add action items | ✓ | ✓ | ✓ | — |
| Complete an action | ✓ | ✓ | When commander or owner | — |

## Run with Docker and PostgreSQL

Install Docker Desktop, enter this project directory, then run:

```bash
docker compose up --build
```

The web container waits for PostgreSQL, applies migrations, creates the demo data, and starts Gunicorn. Open <http://localhost:8000>.

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

To delete the local Docker database as well, run `docker compose down -v`.

## Environment variables

| Variable | Required in production | Purpose |
|---|:---:|---|
| `DJANGO_SECRET_KEY` | Yes | Long, random application secret |
| `DJANGO_DEBUG` | Yes | Set to `False` in production |
| `DJANGO_ALLOWED_HOSTS` | Yes | Comma-separated deployment hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | For HTTPS forms | Comma-separated origins including `https://` |
| `DATABASE_URL` | Recommended | PostgreSQL connection URL; SQLite is the local fallback |
| `DJANGO_TIME_ZONE` | No | Defaults to `Asia/Kolkata` |
| `DJANGO_SECURE_SSL_REDIRECT` | No | Defaults to `True` when debug is disabled |

`config/settings.py` also enables secure cookies, HSTS, proxy HTTPS handling, MIME sniffing protection, frame denial, and WhiteNoise's manifest storage when `DJANGO_DEBUG=False`.

## JSON API

Sign in through the web app, then use these read-only, tenant-scoped endpoints:

| Endpoint | Purpose | Filters |
|---|---|---|
| `/api/summary/` | Service, incident, SLA, and MTTR metrics | — |
| `/api/services/` | Service status and active-incident counts | — |
| `/api/incidents/` | Incident history and resolution clocks | `status`, `severity` |
| `/api/incidents/<id>/` | Timeline, responders, and action items | — |

For local use, sign in through the browser and open <http://127.0.0.1:8000/api/summary/> in the same session. Every API query derives the organization from the authenticated membership; clients cannot select another tenant.

## Common development commands

```bash
# Run configuration and migration checks
python manage.py check
python manage.py makemigrations --check --dry-run

# Run tests and enforce the coverage gate
coverage run manage.py test
coverage report --fail-under=88

# Format and lint
ruff format .
ruff check .

# Create a real administrator
python manage.py createsuperuser

# Refresh the repeatable demo workspace
python manage.py seed_demo

# Collect production static assets
python manage.py collectstatic --noinput
```

## Architecture and tenant isolation

```text
Organization
├── Membership ── User + role
├── Service
│   └── Incident
│       ├── IncidentResponder
│       ├── IncidentUpdate
│       └── ActionItem
└── public status page
```

`Membership` binds one Django user to one `Organization` and supplies role permissions. The `workspace_required` decorator resolves that membership for every authenticated application and API request. Each query filters by `request.organization`; every form constrains foreign-key choices to the same tenant; model validation rejects cross-tenant relationships as a final defense.

Mutating incident workflows use database transactions when multiple records must remain consistent. Service state is recalculated from active incident severity, while an explicit maintenance state remains intact when no incident is active. Public status output begins from a public-service queryset and fetches only timeline updates explicitly marked public.

For a larger production deployment, add organization invitations, SSO, an append-only audit stream, background notifications, API tokens, rate limiting, file evidence storage, and PostgreSQL row-level security.

## Project structure

```text
2026-08-30-opsbeacon-incident-management/
├── config/                         # Settings, root URLs, WSGI and ASGI
├── operations/                     # Tenant models, forms, views, APIs and tests
│   ├── management/commands/seed_demo.py
│   ├── migrations/
│   └── static/operations/app.css
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
3. Set the Blueprint root directory to `daily-saas-products/2026-08-30-opsbeacon-incident-management`.
4. Review the generated web service and PostgreSQL database, then deploy.
5. After deployment, run `python manage.py createsuperuser` in the Render shell.
6. Do not seed demo credentials into a real customer environment.

The blueprint generates the secret key, disables debug mode, configures HTTPS origins, installs dependencies, collects static files, runs migrations, and starts Gunicorn. Confirm the final hostname matches both `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` if you rename the service.

## License

This product uses the repository's MIT license.
