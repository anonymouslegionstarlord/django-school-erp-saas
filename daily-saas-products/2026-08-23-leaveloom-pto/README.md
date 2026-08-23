# LeaveLoom — multi-tenant leave management SaaS

LeaveLoom is a portfolio-ready workforce leave and PTO application for growing teams. Employees can request time away, monitor balances, and see the shared calendar; managers can review requests with a clear audit trail. Every company's data is isolated by an authenticated workspace boundary.

## Functional MVP

- Self-service company signup and secure Django authentication
- Owner, manager, and employee membership roles
- Annual allowances and weekend-aware business-day calculations
- Configurable paid and unpaid leave types
- Leave requests with reasons, date ranges, statuses, reviewer, note, and timestamps
- Overlapping-request prevention and database-enforced valid date ranges
- Manager approval queue with approve/reject decisions
- Self-approval prevention and employee cancellation of pending requests
- Personal balance dashboard, team availability, request history, and shared monthly calendar
- Role-aware, tenant-scoped summary, request, and calendar JSON APIs
- Responsive interface, repeatable sample data, automated tests, Docker/PostgreSQL, Render, CI, and secure defaults

## First-time setup — Windows

Install [Python 3.12](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win), then run in PowerShell:

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-23-leaveloom-pto
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and activate again. Open <http://127.0.0.1:8000>.

## First-time setup — macOS or Linux

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-08-23-leaveloom-pto
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

Run `python manage.py seed_demo`, then use either role:

| Role | Username | Password |
|---|---|---|
| People operations owner | `demo_peopleops` | `DemoPass123!` |
| Manager | `demo_manager` | `DemoPass123!` |
| Employee | `demo_employee` | `DemoPass123!` |

The idempotent command creates Northstar Digital, four leave types, three team members, an approval queue, approved history, and upcoming calendar entries. It resets only these demo passwords and does not duplicate records. Never run it against production.

You can also create a separate owner workspace at `/signup/`; annual and sick leave types are added automatically.

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

The read-only MVP endpoints use the authenticated browser session:

| Method | Endpoint | Access and result |
|---|---|---|
| `GET` | `/api/summary/` | Personal allowance, usage, balance, and team queue count |
| `GET` | `/api/requests/` | Owners/managers see the tenant; employees see only their requests |
| `GET` | `/api/calendar/` | Approved leave for the current tenant |

Every endpoint derives the organization and role from the authenticated membership. Browser forms provide CSRF-protected write operations.

## Architecture and tenant isolation

```text
Authenticated User ──1 Membership *──1 Organization
                             │                 ├── LeaveType
                  role + allowance            └── LeaveRequest
                                                       ├── requester
                                                       └── reviewer + audit fields
```

The `workspace_required` decorator resolves membership and organization from the signed-in user. Tenant IDs are never trusted from a URL, form, or API parameter. Every query, detail lookup, mutation, leave-type form choice, calendar entry, and API result includes the resolved organization boundary. Cross-tenant identifiers return 404 or fail validation.

Role checks are applied server-side. Employees cannot access team request data or approve requests; managers and owners cannot approve their own requests. The date-range database constraint protects direct model writes, while the form adds friendly ordering and overlap errors.

Business days currently exclude Saturdays and Sundays. Production extensions can add organization-specific holidays, half-days, accrual schedules, carry-over policies, and regional working weeks.

## Environment variables

| Variable | Production | Purpose |
|---|---:|---|
| `DJANGO_SECRET_KEY` | Required | Long random signing secret |
| `DJANGO_DEBUG` | Set `False` | Local diagnostics only |
| `DJANGO_ALLOWED_HOSTS` | Required | Comma-separated deployed hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Required for HTTPS forms | Full comma-separated HTTPS origins |
| `DATABASE_URL` | Recommended | PostgreSQL URL; empty uses SQLite |
| `DJANGO_TIME_ZONE` | Optional | Defaults to `Asia/Kolkata` |
| `DJANGO_SECURE_SSL_REDIRECT` | Optional | Defaults to `True` outside debug mode |

Django reads process environment variables; it does not silently load `.env`. Use your platform's secret manager for real values. `.env.example` contains placeholders only.

## Secure defaults

- Authentication protects every dashboard, business route, and API.
- Password validation, CSRF middleware, HttpOnly cookies, MIME-sniffing protection, and clickjacking denial are enabled.
- Production mode enables secure cookies, proxy-aware HTTPS, SSL redirect, one-year HSTS including subdomains and preload, and hashed compressed static assets.
- Server-side tenancy and roles protect both reads and writes.
- `.env`, databases, virtual environments, caches, test coverage, logs, and generated static files are ignored.

## Deployment

### Render blueprint

1. Create a Render Blueprint from this repository and `daily-saas-products/2026-08-23-leaveloom-pto/render.yaml`.
2. Set the root directory to `daily-saas-products/2026-08-23-leaveloom-pto` if it is not inferred.
3. Replace the example hostname in allowed hosts and CSRF origins with the assigned HTTPS hostname.
4. Deploy, then create an owner at `/signup/` or run `python manage.py createsuperuser` in the service shell.

The blueprint provisions PostgreSQL, generates a secret, installs dependencies, applies migrations, collects static files, and starts Gunicorn. Review the provider's current plan availability before production use.

### Other Linux platforms

Configure the variables above, provision PostgreSQL, and run:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
```

Run migrations once as a release step. Enable backups, TLS, monitoring, email delivery, and `DJANGO_DEBUG=False` before handling real employee data.

## Project layout

```text
config/                   Django settings and entry points
leave/                    Models, forms, views, APIs, admin, tests, and seed command
leave/migrations/         Versioned schema
templates/                Responsive server-rendered experience
static/leave/             LeaveLoom design system
Dockerfile                Non-root production image
docker-compose.yml        Local Django and PostgreSQL stack
render.yaml               Render deployment blueprint
```

## Production extensions

Useful next steps include invitations, multiple approvers, holiday calendars, half-days, accrual and carry-over policies, email/Slack notifications, CSV exports, SSO, audit-event retention, and calendar feeds.

## License

This product follows the repository's MIT license.
