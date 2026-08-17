# ClientFlow — Multi-tenant CRM SaaS

ClientFlow is a full-stack Django CRM for small sales and service teams. Each account belongs to an isolated workspace where users can manage contacts, move deals through a pipeline, log activities, and inspect live sales metrics.

## Features

- Self-service signup creates a user and owner workspace atomically
- Tenant-aware contacts, deals, activities, dashboard, and API queries
- Five-stage sales pipeline: lead, qualified, proposal, won, and lost
- Calls, emails, meetings, and notes attached to deals
- Responsive, mobile-friendly server-rendered frontend
- JSON summary, contacts, and deals endpoints under `/api/v1/`
- Repeatable demo-data command with realistic Indian-market sample values
- SQLite for a zero-configuration first run; PostgreSQL ready for Docker and production
- CSRF protection, password validators, secure production cookies, HSTS, host validation, and no committed secrets
- 12 automated tests focused on tenant isolation and core workflows

## Stack and architecture

| Layer | Choice |
|---|---|
| Backend | Python 3.12, Django 5.2 LTS |
| Frontend | Django templates and custom responsive CSS |
| Database | SQLite locally, PostgreSQL in Docker/production |
| Production | Gunicorn, WhiteNoise, Docker, Render blueprint |
| Quality | Django TestCase, Coverage, Ruff |

`Organization` is the tenant boundary. A `Membership` maps each Django user to one organization. Every authenticated view obtains that organization from the membership, and every contact, deal, and activity query includes it. Foreign tenant object IDs return `404` instead of leaking whether the object exists.

## First-time setup — Windows

Use PowerShell on Windows 10 or 11.

1. Install [Python 3.12](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win). Select **Add Python to PATH** during Python installation.
2. Clone the repository and enter this product:

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-17-clientflow-crm
```

3. Create and activate a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and activate again.

4. Install, configure, migrate, seed, and run:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open <http://127.0.0.1:8000>.

## First-time setup — macOS or Linux

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-08-17-clientflow-crm
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open <http://127.0.0.1:8000>.

## Demo credentials

After `python manage.py seed_demo`:

```text
Username: demo_owner
Password: DemoPass123!
```

These credentials are for local demonstration only. `seed_demo` resets this password and demo records, so never run it against a real production database.

## Docker setup

From this product folder:

```bash
docker compose up --build
```

In a second terminal:

```bash
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000>. Stop with `docker compose down`; add `-v` only when you intentionally want to delete local PostgreSQL data.

## Environment variables

| Variable | Production | Purpose |
|---|---:|---|
| `DJANGO_SECRET_KEY` | Required | Long, random application secret |
| `DJANGO_DEBUG` | Set `False` | Debug output toggle |
| `DJANGO_ALLOWED_HOSTS` | Required | Comma-separated hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Usually required | Comma-separated HTTPS origins |
| `DATABASE_URL` | Recommended | PostgreSQL URL; empty uses SQLite |
| `DJANGO_TIME_ZONE` | Optional | Defaults to `Asia/Kolkata` |

Never commit `.env`. The supplied `.env.example` contains names and safe placeholders only.

## Common commands

```bash
python manage.py createsuperuser
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
coverage run manage.py test && coverage report
ruff check .
python manage.py collectstatic --noinput
```

## API endpoints

Sign in with the browser session, then open:

- `GET /api/v1/summary/` — tenant-level counts and open pipeline value
- `GET /api/v1/contacts/` — tenant contacts
- `GET /api/v1/deals/` — tenant deals with contact and stage data

All endpoints require authentication and apply the same workspace isolation as the web interface.

## Deployment

### Render blueprint

1. Push the repository to GitHub.
2. In Render, create a Blueprint and select this repository.
3. Set the Blueprint root directory to `daily-saas-products/2026-08-17-clientflow-crm` if prompted.
4. Review the web service and PostgreSQL database from `render.yaml`.
5. Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to the final Render hostname.
6. Deploy, then run `python manage.py migrate` and `python manage.py createsuperuser` in the Render shell.

For another Docker host, build this folder, supply a PostgreSQL `DATABASE_URL`, set all production variables, and run the image. The container starts migrations and Gunicorn automatically.

## Data model

```text
User ──1 Membership *──1 Organization
                              │
                              ├──* Contact
                              │      └──* Deal
                              │             └──* Activity
                              └─────────────── tenant boundary
```

## Important production extension

The MVP supports one workspace membership per user. A mature version can change `Membership.user` to a foreign key and add an active-workspace selector, invitations, role permissions, audit logs, pagination, token-based API authentication, and asynchronous reminders.
