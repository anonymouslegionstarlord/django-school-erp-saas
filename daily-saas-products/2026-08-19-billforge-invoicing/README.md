# BillForge — Multi-tenant Invoicing SaaS

BillForge is a full-stack Django billing platform for freelancers and small teams. Each business gets an isolated workspace for clients, invoices, line items, tax calculations, partial payments, balances, and overdue tracking.

## Functional MVP

- Self-service signup creates an owner and business workspace atomically
- Client directory with tenant-unique email addresses
- Draft, sent, paid, and void invoice lifecycle
- Quantity, unit-price, subtotal, configurable tax, total, paid, and balance calculations
- Partial-payment recording with overpayment protection and automatic paid status
- Overdue detection and cash-flow dashboard
- Search and status filters
- Tenant-scoped summary, client, and invoice JSON APIs
- Responsive frontend, demo data, SQLite/PostgreSQL, Docker, Render, and secure production defaults
- 15 automated tests covering calculations, payments, tenant isolation, APIs, and signup

## First-time setup — Windows

Install Python 3.12 and Git, then use PowerShell:

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-19-billforge-invoicing
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

If activation is blocked, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. Open <http://127.0.0.1:8000>.

## First-time setup — macOS or Linux

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-08-19-billforge-invoicing
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

## Demo login

```text
Username: demo_billing
Password: DemoPass123!
```

Run `python manage.py seed_demo` first. The command resets demo records and the password; never run it against production.

## Docker

```bash
docker compose up --build
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000>. Stop with `docker compose down`.

## Configuration

| Variable | Production use |
|---|---|
| `DJANGO_SECRET_KEY` | Required long random secret |
| `DJANGO_DEBUG` | Set to `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins |
| `DATABASE_URL` | PostgreSQL URL; empty uses SQLite |
| `DJANGO_TIME_ZONE` | Defaults to `Asia/Kolkata` |

Never commit `.env`; `.env.example` contains placeholders only.

## Common commands

```bash
python manage.py createsuperuser
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
coverage run manage.py test && coverage report
ruff check .
```

## API

After browser sign-in:

- `GET /api/v1/summary/`
- `GET /api/v1/invoices/`
- `GET /api/v1/clients/`

All responses are limited to the signed-in business workspace.

## Architecture

```text
User ──1 Membership *──1 Organization
                              ├──* Client ──* Invoice ──* LineItem
                              │                   └──────* Payment
                              └──────────────── tenant boundary
```

An `Organization` is the tenant boundary. Every client, invoice, payment, detail lookup, mutation, and API query includes it. Foreign-tenant IDs return `404`. Monetary values use `Decimal`, and invoice totals are derived from stored line items and payments.

## Render deployment

Create a Render Blueprint from the repository, set the root directory to `daily-saas-products/2026-08-19-billforge-invoicing`, and use `render.yaml`. Set the final allowed host and CSRF origin, deploy, then run `python manage.py migrate` and `python manage.py createsuperuser` in the Render shell.

Production extensions can add PDF generation, email delivery, recurring invoices, payment-gateway webhooks, credit notes, audit logs, multi-currency support, invitations, and token authentication.
