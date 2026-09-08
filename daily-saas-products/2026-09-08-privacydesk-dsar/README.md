# PrivacyDesk — Data Rights Request SaaS

PrivacyDesk is a portfolio-ready, multi-tenant Django application for handling data subject access requests (DSARs). It turns intake, identity verification, data collection, final review and fulfilment into an accountable workflow with role controls and privacy-safe public tracking.

## Features

- Isolated organization workspaces and secure Django authentication
- Owner, privacy manager, analyst and read-only viewer roles
- Data-subject directory and access, deletion, correction, portability and objection requests
- GDPR, UK GDPR, CCPA, India DPDP and custom-jurisdiction labels
- Deadline radar, overdue detection and operational metrics
- Guarded lifecycle: received → verifying → in progress → final review → fulfilled/rejected
- Task assignment, completion gates and auditable public/private updates
- Privacy-safe public tracking that never exposes names, emails or internal notes
- Tenant-scoped JSON request API and controlled workflow mutation endpoint
- Responsive UI, SQLite development, PostgreSQL production, Docker and Render blueprint

## First run — Windows

Install Python 3.12 and Git, then use PowerShell:

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-09-08-privacydesk-dsar
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

If activation is blocked, run `Set-ExecutionPolicy -Scope Process Bypass` first.

## First run — macOS or Linux

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-09-08-privacydesk-dsar
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open <http://127.0.0.1:8000>.

## Demo accounts

All accounts use password `DemoPass123!`.

| Role | Username | Capability |
|---|---|---|
| Owner | `demo_privacy` | Full workspace and decision access |
| Privacy manager | `demo_privacy_manager` | Workflow and decision access |
| Analyst | `demo_privacy_analyst` | Intake, tasks and review preparation |
| Viewer | `demo_privacy_viewer` | Read-only reporting |

Run `python manage.py seed_demo` again at any time; it is idempotent.

## Docker

```bash
docker compose up --build -d
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000>. Stop with `docker compose down`; add `-v` only when you intentionally want to erase the database volume.

## API

Session-authenticated endpoints:

- `GET /api/requests/` — tenant-scoped request summary
- `POST /api/requests/<id>/transition/` — JSON workflow mutation (`status`, `note`, `delivery_reference`)

Browser mutations require Django's CSRF token. Authorization and lifecycle rules are enforced in the service layer, not only in the UI.

## Architecture

`Organization` and `Membership` establish the tenant boundary. `DataSubject`, `PrivacyRequest`, `RequestTask` and `RequestEvent` form the domain model. Views scope every lookup to the authenticated membership's organization. Atomic service functions lock workflow rows and enforce role, evidence and completion gates. Django templates and a dependency-free responsive stylesheet provide the frontend.

## Environment and secure defaults

Copy `.env.example` values into your host environment; the app intentionally does not auto-load `.env`. Set a long random `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, real allowed hosts, HTTPS CSRF origins and `DATABASE_URL` in production. Production enables secure cookies, HTTPS redirect, HSTS, clickjacking protection, content-type sniffing protection and compressed manifest static files. Never use demo data or credentials in production.

## Common commands

```bash
python manage.py createsuperuser
python manage.py makemigrations --check --dry-run
python manage.py check
ruff format --check .
ruff check .
coverage run manage.py test
coverage report
python manage.py collectstatic --noinput
```

Install `requirements-dev.txt` before running lint and coverage commands.

## Deploy to Render

Create a Render Blueprint from the repository's `render.yaml`. After the first deployment, update `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` with the exact HTTPS host, then create an administrator with `python manage.py createsuperuser` in a Render shell. Do not run `seed_demo` in production.

## MVP boundaries

PrivacyDesk stores operational metadata, not identity documents or response archives. A production rollout should use encrypted object storage, malware scanning, expiring signed download links, SSO/MFA, immutable audit export, retention automation and jurisdiction-specific legal review.
