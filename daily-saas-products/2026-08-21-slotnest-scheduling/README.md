# SlotNest — appointment scheduling SaaS

SlotNest is a portfolio-ready, multi-tenant scheduling workspace for consultants, wellness studios, salons, clinics, and other service businesses. Teams can manage services and customers, book appointments, run a daily schedule, update visit status, and inspect tenant-scoped JSON APIs from a polished responsive interface.

## Product features

- Self-service owner signup and secure Django authentication
- Organization workspaces with server-side tenant isolation on every business query
- Service catalog with duration, price, color, and active state
- Customer directory with contact details, notes, and appointment counts
- Staff-aware appointment booking with duplicate-start protection
- Daily schedule and an operational dashboard with appointments, upcoming work, completions, and recognized revenue
- Confirmed, checked-in, completed, cancelled, and no-show workflow
- Session-authenticated JSON APIs for summary, appointments, and services
- Repeatable sample-data command and local demo credentials
- Responsive, accessible Django-template frontend without a JavaScript build step
- SQLite development, PostgreSQL production, WhiteNoise static assets, Gunicorn, Docker Compose, Render blueprint, CI, Ruff, and Coverage

## First-time setup — Windows

Install [Python 3.12](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win), then run in PowerShell:

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-21-slotnest-scheduling
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

Install Python 3.12 and Git, then run:

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-08-21-slotnest-scheduling
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

## Demo account

After `python manage.py seed_demo`, sign in with:

```text
Username: demo_scheduler
Password: DemoPass123!
```

The seed command is idempotent and resets this local-only password. It creates Northstar Wellness, three services, three customers, and a useful mix of today's and tomorrow's appointments. Do not run it against a real production database.

You can also select **Create workspace** and register a completely separate tenant.

## Docker setup

With Docker Desktop or Docker Engine installed, run from this product directory:

```bash
docker compose up --build
```

In another terminal, seed the demo workspace:

```bash
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000>. The compose stack uses PostgreSQL 16 with a named volume. Stop it with `docker compose down`; add `-v` only when you intentionally want to delete local database data.

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

The APIs use the same authenticated browser session as the web interface and always derive the workspace from the signed-in user's membership:

| Method | Endpoint | Result |
|---|---|---|
| `GET` | `/api/summary/` | Workspace counts and upcoming workload |
| `GET` | `/api/appointments/` | Tenant appointments with customer, staff, timing, status, and price |
| `GET` | `/api/services/` | Tenant service catalog |

Example after signing in: `curl -b cookies.txt http://127.0.0.1:8000/api/appointments/`. These endpoints are intentionally read-only in the MVP; browser forms provide CSRF-protected writes.

## Architecture and tenancy

```text
Browser / API client
        |
  Django auth session
        |
workspace_required decorator -> Membership -> Organization
        |
tenant-scoped views and forms
        |
Organization-owned Service, Customer, Appointment
        |
SQLite locally / PostgreSQL in production
```

`Membership` maps each Django user to one organization and role. Each business record has an explicit `organization` foreign key. Views never accept a tenant identifier from the browser; they resolve it from the authenticated membership and filter every queryset. Appointment form choices are also tenant-scoped, preventing cross-workspace foreign-key submission. Detail and status routes include the organization in object lookup, so another tenant's primary key returns 404.

The MVP prevents two appointments for the same staff member at the exact same start time through both form validation and a database constraint. A production calendar can extend this with full interval-overlap checks, recurring appointments, invitations, notifications, and audit logging.

## Environment configuration

| Variable | Production | Purpose |
|---|---:|---|
| `DJANGO_SECRET_KEY` | Required | Long random signing secret; never commit it |
| `DJANGO_DEBUG` | Set `False` | Enables local debug only |
| `DJANGO_ALLOWED_HOSTS` | Required | Comma-separated deployed hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Required for HTTPS forms | Comma-separated full HTTPS origins |
| `DATABASE_URL` | Recommended | PostgreSQL URL; empty uses local SQLite |
| `DJANGO_TIME_ZONE` | Optional | Defaults to `Asia/Kolkata` |
| `DJANGO_SECURE_SSL_REDIRECT` | Optional | Defaults to `True` outside debug mode |

The `.env.example` is documentation; Django reads environment variables supplied by your shell, container, or hosting platform. It does not silently load `.env`. Use your platform's secret manager in production.

## Secure defaults

- Django password validators, CSRF middleware, HttpOnly cookies, clickjacking denial, and MIME sniffing protection are enabled.
- Production mode enables secure cookies, HTTPS redirect, proxy-aware TLS, one-year HSTS (including subdomains and preload), and manifest-hashed compressed static files.
- Authentication is required for every dashboard, business route, and API endpoint.
- Secrets, environment files, SQLite databases, coverage output, caches, virtual environments, and generated static files are ignored.
- The sample password is confined to the explicit demo command and must never be used in production.

## Deployment

### Render blueprint

1. Fork or push this repository to your GitHub account.
2. In Render, create a Blueprint from `daily-saas-products/2026-08-21-slotnest-scheduling/render.yaml`.
3. Set the service root directory to `daily-saas-products/2026-08-21-slotnest-scheduling` if Render does not infer it.
4. Replace the example hostname in `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` with the assigned hostname.
5. Deploy, then run `python manage.py createsuperuser` in the Render shell or create an owner from `/signup/`.

The blueprint provisions PostgreSQL, generates the secret, installs dependencies, runs migrations, collects static assets, and starts Gunicorn. Review the database plan before production use; provider offerings can change.

### Other Linux platforms

Configure the environment variables above, provision PostgreSQL, and use:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
```

Run migrations as a release step rather than concurrently on multiple application instances. Terminate TLS at the platform proxy, keep `DJANGO_DEBUG=False`, use backups, and add monitoring before serving real customer data.

## Project layout

```text
config/                   Django settings and URL configuration
scheduler/                Domain models, forms, views, admin, tests, and seed command
scheduler/migrations/     Versioned database schema
templates/                Responsive server-rendered interface
static/scheduler/         Product design system and responsive CSS
Dockerfile                Production-like image
docker-compose.yml        Local Django + PostgreSQL stack
render.yaml               Render deployment blueprint
```

## License

This product follows the repository's MIT license.
