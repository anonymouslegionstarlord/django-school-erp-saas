# DeskPulse — Multi-tenant Help Desk SaaS

DeskPulse is a full-stack Django customer-support platform for small teams. Each company gets an isolated workspace for customers, support tickets, priority-aware response targets, assignment, threaded replies, internal notes, dashboard metrics, and JSON APIs.

## Functional MVP

- Self-service registration creates an owner account and support workspace atomically
- Customer directory with per-workspace unique email addresses and ticket counts
- Searchable ticket queue with status and priority filters
- Open, in-progress, waiting, and resolved workflows
- Low, medium, high, and urgent priorities with automatic response deadlines
- Agent assignment, customer replies, and internal team notes
- Overdue and urgent workload indicators on a responsive dashboard
- Tenant-scoped summary, customer, and ticket JSON endpoints
- Repeatable realistic demo data
- SQLite locally; PostgreSQL, Docker, Gunicorn, WhiteNoise, and Render support
- Secure cookies, CSRF, host validation, HSTS, password validators, and environment-based secrets
- 15 automated tests emphasizing tenant isolation and support workflows

## Technology and architecture

| Layer | Technology |
|---|---|
| Backend | Python 3.12 and Django 5.2 LTS |
| Frontend | Django templates and custom responsive CSS |
| Database | SQLite locally; PostgreSQL in Docker/production |
| Production | Gunicorn, WhiteNoise, Docker, Render blueprint |
| Quality | Django TestCase, Coverage, Ruff |

`Organization` is the tenant boundary. A `Membership` links a Django user to a support workspace. Every authenticated view obtains the organization from that membership, and every customer, ticket, reply, detail lookup, and API query includes that organization. Attempts to use an object ID from another tenant return `404`.

## First-time setup — Windows

Use PowerShell on Windows 10 or 11.

1. Install [Python 3.12](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win). Select **Add Python to PATH** during Python installation.
2. Clone the portfolio and enter DeskPulse:

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-18-deskpulse-helpdesk
```

3. Create and activate an isolated environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and activate again.

4. Install and start the project:

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
cd django-school-erp-saas/daily-saas-products/2026-08-18-deskpulse-helpdesk
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

After running `python manage.py seed_demo`:

```text
Username: demo_agent
Password: DemoPass123!
```

These credentials are only for local demonstration. `seed_demo` resets this password and the demo workspace records, so do not use that command against a real production database.

## Run with Docker

From the DeskPulse folder:

```bash
docker compose up --build
```

In a second terminal, add sample data:

```bash
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000>. Stop without deleting data using `docker compose down`. Add `-v` only when you intentionally want to erase the local PostgreSQL volume.

## Environment variables

| Variable | Production | Purpose |
|---|---:|---|
| `DJANGO_SECRET_KEY` | Required | Long random application secret |
| `DJANGO_DEBUG` | Set `False` | Debug-mode toggle |
| `DJANGO_ALLOWED_HOSTS` | Required | Comma-separated hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Usually required | Comma-separated HTTPS origins |
| `DATABASE_URL` | Recommended | PostgreSQL connection URL; empty selects SQLite |
| `DJANGO_TIME_ZONE` | Optional | Defaults to `Asia/Kolkata` |

Never commit `.env`. `.env.example` contains names and safe placeholders only.

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

## JSON API

Sign in through the web application, then use:

- `GET /api/v1/summary/` — customer, active-ticket, and overdue counts
- `GET /api/v1/tickets/` — tenant tickets with customer, priority, status, assignee, and target
- `GET /api/v1/customers/` — tenant customer directory

The API uses the authenticated browser session and applies the same tenant isolation as the interface.

## Deployment with Render

1. Push this repository to GitHub.
2. In Render, create a Blueprint from the repository.
3. Use `daily-saas-products/2026-08-18-deskpulse-helpdesk` as the root directory if requested.
4. Review the web service and PostgreSQL database described by `render.yaml`.
5. Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to the final hostname.
6. Deploy, then run `python manage.py migrate` and `python manage.py createsuperuser` in the Render shell.

For another Docker platform, build this folder, provide a PostgreSQL `DATABASE_URL`, use production environment values, and launch the image. The container runs migrations before starting Gunicorn.

## Data model

```text
User ──1 Membership *──1 Organization
                              │
                              ├──* Customer
                              │      └──* Ticket
                              │             └──* Reply
                              └─────────────── tenant boundary
```

## Natural next steps

A production evolution can add customer email ingestion, invitations and multi-workspace membership, fine-grained roles, attachments with malware scanning, outbound notifications, audit logs, pagination, token authentication, and asynchronous SLA escalation jobs.
