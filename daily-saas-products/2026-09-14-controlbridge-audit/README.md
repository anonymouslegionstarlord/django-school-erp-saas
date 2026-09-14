# ControlBridge — Internal Controls Audit SaaS

ControlBridge is a portfolio-ready, multi-tenant Django application for managing internal-control findings and remediation. It turns intake, risk triage, remediation, final review and fulfilment into an accountable workflow with role controls and audit-safe public tracking.

## Features

- Isolated organization workspaces and secure Django authentication
- Owner, audit manager, auditor and read-only viewer roles
- Control-area register and control gap, policy breach, access risk, evidence gap and third-party risk findings
- SOX, ISO 27001, SOC 2, PCI DSS and internal-policy labels
- Deadline radar, overdue detection and operational metrics
- Guarded lifecycle: open → triage → remediation → final review → resolved/risk accepted
- Task assignment, completion gates and auditable public/private updates
- Stakeholder-safe public tracking that never exposes names, emails or internal notes
- Tenant-scoped JSON finding API and controlled workflow mutation endpoint
- Responsive UI, SQLite development, PostgreSQL production, Docker and Render blueprint

## First run — Windows

Install Python 3.12 and Git, then use PowerShell:

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-09-14-controlbridge-audit
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
cd django-school-erp-saas/daily-saas-products/2026-09-14-controlbridge-audit
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
| Owner | `demo_control` | Full workspace and decision access |
| Audit manager | `demo_control_manager` | Workflow and decision access |
| Auditor | `demo_control_auditor` | Intake, tasks and review preparation |
| Viewer | `demo_control_viewer` | Read-only reporting |

Run `python manage.py seed_demo` again at any time; it is idempotent.

## Docker

Copy `.env.example` to `.env`, replace `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`, then run:

```bash
docker compose up --build -d
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000>. Stop with `docker compose down`; add `-v` only when you intentionally want to erase the database volume.

## API

Session-authenticated endpoints:

- `GET /api/findings/` — tenant-scoped finding summary
- `POST /api/findings/<id>/transition/` — JSON workflow mutation (`status`, `note`, `evidence_reference`)

Browser mutations require Django's CSRF token. Authorization and lifecycle rules are enforced in the service layer, not only in the UI.

## Architecture

`Organization` and `Membership` establish the tenant boundary. `ControlArea`, `AuditFinding`, `RemediationTask` and `FindingEvent` form the domain model. Views scope every lookup to the authenticated membership's organization. Atomic service functions lock workflow rows and enforce role, evidence and completion gates. Django templates and a dependency-free responsive stylesheet provide the frontend.

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

ControlBridge stores evidence metadata, not sensitive evidence files. A production rollout should use encrypted object storage, malware scanning, expiring signed download links, SSO/MFA, immutable audit export, retention automation and framework-specific legal review.
