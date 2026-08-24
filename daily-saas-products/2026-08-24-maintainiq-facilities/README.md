# MaintainIQ — facilities maintenance SaaS

MaintainIQ is a portfolio-ready, multi-tenant maintenance operations platform for coworking operators, offices, retail chains, property teams, and workshops. It connects locations, equipment, service requests, technicians, deadlines, labor, and cost history in one responsive Django workspace.

## Functional MVP

- Self-service owner signup and secure Django session authentication
- Owner, technician, and requester roles
- Organization-isolated sites, assets, work orders, and service logs
- Asset register with tags, categories, condition, location, and installation dates
- Work-order priorities, six-stage status workflow, due targets, assignments, and completion timestamps
- Requester-limited views; owners and technicians see the tenant operations queue
- Overdue/SLA detection, urgent queue, asset-health alerts, and completion metrics
- Costed work logs with technician, notes, hours, cost, and timestamp
- Tenant-safe work-order form validation, including asset/site consistency
- Role-aware summary, work-order, and asset JSON APIs
- Repeatable demo data, automated tests, Docker/PostgreSQL, Render, CI, and secure defaults

## First-time setup — Windows

Install [Python 3.12](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win). Run in PowerShell:

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-24-maintainiq-facilities
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in the same terminal and activate again. Open <http://127.0.0.1:8000>.

## First-time setup — macOS or Linux

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-08-24-maintainiq-facilities
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

## Demo accounts

Run `python manage.py seed_demo`, then use any workflow role:

| Role | Username | Password |
|---|---|---|
| Facilities owner | `demo_facilities` | `DemoPass123!` |
| Technician | `demo_technician` | `DemoPass123!` |
| Requester | `demo_requester` | `DemoPass123!` |

The idempotent command creates Helios Workspaces, two sites, three assets, three work orders, an overdue critical job, and a costed technician log. It resets these local demo passwords without duplicating records. Never run it against production.

## Docker setup

With Docker Desktop or Docker Engine installed:

```bash
docker compose up --build
```

In another terminal:

```bash
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000>. PostgreSQL data persists in `postgres_data`. Stop with `docker compose down`; add `-v` only when intentionally deleting local data.

## Common commands

```bash
python manage.py runserver
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py check --deploy
python manage.py test
coverage run manage.py test
coverage report
ruff format --check .
ruff check .
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## JSON API

The read-only APIs use the authenticated session:

| Method | Endpoint | Access and result |
|---|---|---|
| `GET` | `/api/summary/` | Active, overdue, critical, and asset metrics |
| `GET` | `/api/work-orders/` | Tenant queue for managers; only personally requested work for requesters |
| `GET` | `/api/assets/` | Tenant asset register with location and condition |

Browser forms provide CSRF-protected writes. The API derives tenant and role from the signed-in membership rather than accepting them as parameters.

## Architecture and tenancy

```text
Authenticated User ──1 Membership *──1 Organization
                             │                 ├── Site ── Asset
                        role boundary          └── WorkOrder ── WorkLog
                                                      │           │
                                               requester/tech   author + cost
```

The `workspace_required` decorator resolves membership and organization from the authenticated user. Every list, detail, mutation, form choice, and API query includes that organization. Cross-tenant IDs return 404 or fail choice validation. Asset/site consistency is validated server-side.

Requesters see and open their own work. Owners and technicians can manage the tenant queue, assign eligible staff, change status and due targets, and add service logs. Completion automatically records a timestamp; reopening clears it. Overdue state excludes completed and cancelled work.

## Environment variables

| Variable | Production | Purpose |
|---|---:|---|
| `DJANGO_SECRET_KEY` | Required | Long random signing secret |
| `DJANGO_DEBUG` | Set `False` | Local diagnostics only |
| `DJANGO_ALLOWED_HOSTS` | Required | Comma-separated deployed hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Required for HTTPS forms | Full HTTPS origins |
| `DATABASE_URL` | Recommended | PostgreSQL URL; empty uses SQLite |
| `DJANGO_TIME_ZONE` | Optional | Defaults to `Asia/Kolkata` |
| `DJANGO_SECURE_SSL_REDIRECT` | Optional | Defaults to `True` outside debug mode |

Django reads process environment variables and does not silently load `.env`. Use platform secrets for real values; `.env.example` is documentation only.

## Secure defaults

- Authentication protects every dashboard, business route, and API.
- Server-side role and organization checks guard reads and writes.
- Django password validators, CSRF protection, HttpOnly cookies, MIME-sniffing protection, and clickjacking denial are enabled.
- Production mode enables secure cookies, proxy-aware HTTPS, SSL redirect, one-year HSTS with subdomains and preload, and hashed compressed static assets.
- `.env`, databases, virtual environments, caches, coverage data, logs, and collected static assets are ignored.

## Deployment

### Render blueprint

1. Create a Render Blueprint from this repository and `daily-saas-products/2026-08-24-maintainiq-facilities/render.yaml`.
2. Set the root directory to `daily-saas-products/2026-08-24-maintainiq-facilities` if needed.
3. Replace the sample allowed host and CSRF origin with the assigned HTTPS hostname.
4. Deploy, then create an owner through `/signup/` or `python manage.py createsuperuser` in the service shell.

The blueprint provisions PostgreSQL, generates a secret, installs dependencies, runs migrations, collects static assets, and starts Gunicorn. Review the provider's current plans before production use.

### Other Linux platforms

Configure the variables above, provision PostgreSQL, and run:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
```

Run migrations once as a release step. Enable backups, TLS, monitoring, alerting, and `DJANGO_DEBUG=False` before storing real operational data.

## Project layout

```text
config/                      Django settings and entry points
maintenance/                 Domain models, forms, views, APIs, tests, and seed command
maintenance/migrations/      Versioned schema
templates/                   Responsive server-rendered frontend
static/maintenance/          MaintainIQ design system
Dockerfile                   Non-root production image
docker-compose.yml           Local Django and PostgreSQL stack
render.yaml                  Render deployment blueprint
```

## Production extensions

Useful next steps include recurring preventive maintenance, attachments, parts inventory, vendor portals, QR asset labels, notifications, escalation rules, mobile offline mode, approval limits, exports, and detailed audit events.

## License

This product follows the repository's MIT license.
