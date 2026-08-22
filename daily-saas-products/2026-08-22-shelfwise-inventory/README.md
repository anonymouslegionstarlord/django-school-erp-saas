# ShelfWise — inventory and procurement SaaS

ShelfWise is a portfolio-ready, multi-tenant inventory application for small retailers, workshops, wholesalers, and operations teams. It combines a product catalog, suppliers, an auditable stock ledger, reorder alerts, and purchase-order receiving in one responsive Django workspace.

## Functional MVP

- Self-service owner signup and Django session authentication
- Organization workspaces with server-side tenant isolation
- Product catalog with SKU, category, supplier, costs, prices, and reorder points
- Supplier directory with lead times and contact details
- Receipt, issue, and adjustment ledger with operator and timestamp
- Negative-stock prevention and database protection against zero movements
- Purchase orders with lines, expected dates, statuses, and totals
- Atomic, idempotent purchase-order receiving that creates stock receipts once
- Dashboard with units, inventory value, low-stock alerts, inbound orders, and recent activity
- Authenticated tenant-scoped summary, product, and movement JSON APIs
- Repeatable sample data, automated tests, Docker/PostgreSQL, Render, CI, and secure defaults

## First-time setup — Windows

Install [Python 3.12](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win). In PowerShell:

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-22-shelfwise-inventory
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
cd django-school-erp-saas/daily-saas-products/2026-08-22-shelfwise-inventory
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

## Demo login

Run `python manage.py seed_demo`, then sign in with:

```text
Username: demo_inventory
Password: DemoPass123!
```

The idempotent command creates Riverbend Supplies, two suppliers, four products with opening stock, two reorder alerts, and an open purchase order. It resets the local demo password but does not duplicate stock on repeat runs. Never run it against production.

## Docker setup

With Docker Desktop or Docker Engine installed:

```bash
docker compose up --build
```

In another terminal:

```bash
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000>. PostgreSQL data is kept in `postgres_data`. Use `docker compose down` to stop; add `-v` only when intentionally deleting local data.

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

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/summary/` | Product, unit, alert, and open-order counts |
| `GET` | `/api/products/` | SKU balances, reorder state, and stock value |
| `GET` | `/api/movements/` | Tenant stock-ledger activity |

Each endpoint derives its organization from the signed-in membership. Browser forms provide CSRF-protected write operations.

## Architecture and tenant boundary

```text
Authenticated User ──1 Membership *──1 Organization
                                           ├── Supplier ── Product
                                           │                  └── StockMovement
                                           └── PurchaseOrder ── PurchaseOrderItem
```

Every business record carries or inherits an organization boundary. The `workspace_required` decorator resolves the tenant from the authenticated user's membership rather than a browser-supplied identifier. All list queries, detail lookups, mutations, form choices, and APIs include that boundary. Cross-tenant primary keys return 404 or fail form validation.

Stock is calculated from the immutable movement ledger rather than a mutable quantity field. Purchase-order receiving locks the order inside a database transaction, creates one receipt per line, then marks it received. Repeated receiving is a no-op. For high-concurrency production workloads, use PostgreSQL and retain this transactional path.

## Environment variables

| Variable | Production | Purpose |
|---|---:|---|
| `DJANGO_SECRET_KEY` | Required | Long random signing secret |
| `DJANGO_DEBUG` | Set `False` | Local diagnostics only |
| `DJANGO_ALLOWED_HOSTS` | Required | Comma-separated deployed hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Required for HTTPS forms | Full comma-separated HTTPS origins |
| `DATABASE_URL` | Recommended | PostgreSQL URL; empty uses local SQLite |
| `DJANGO_TIME_ZONE` | Optional | Defaults to `Asia/Kolkata` |
| `DJANGO_SECURE_SSL_REDIRECT` | Optional | Defaults to `True` outside debug mode |

Django reads process environment variables; it does not silently load `.env`. The example file is documentation. Configure real values in your shell, container environment, or hosting secret manager.

## Secure defaults

- Authentication gates every dashboard, business route, and API.
- Django password validation, CSRF protection, HttpOnly cookies, MIME-sniffing protection, and clickjacking denial are enabled.
- Production enables secure cookies, proxy-aware HTTPS, SSL redirect, one-year HSTS including subdomains and preload, and manifest-hashed compressed static files.
- Tenant-scoped foreign-key form choices prevent cross-workspace submissions.
- Secrets, `.env`, SQLite databases, virtual environments, caches, coverage artifacts, and generated static files are ignored.

## Deployment

### Render

1. Create a Render Blueprint using this repository and `daily-saas-products/2026-08-22-shelfwise-inventory/render.yaml`.
2. Set the service root directory to `daily-saas-products/2026-08-22-shelfwise-inventory` if needed.
3. Replace the example hostname in allowed hosts and CSRF origins with the assigned HTTPS hostname.
4. Deploy, then create the first owner at `/signup/` or run `python manage.py createsuperuser` in the service shell.

The blueprint provisions PostgreSQL, generates a secret, installs packages, applies migrations, collects static files, and runs Gunicorn. Review the provider's current plans before production use.

### Other Linux platforms

Configure the variables above, provision PostgreSQL, and run:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
```

Run migrations as a single release step. Use managed backups, TLS termination, monitoring, and `DJANGO_DEBUG=False` before storing real business data.

## Project layout

```text
config/                   Django settings and entry points
inventory/                Models, forms, views, APIs, admin, tests, and seed command
inventory/migrations/     Versioned schema
templates/                Responsive server-rendered interface
static/inventory/         Product design system
Dockerfile                Non-root production image
docker-compose.yml        Local Django and PostgreSQL stack
render.yaml               Render deployment blueprint
```

## Production extensions

Useful next steps include multiple warehouse locations, barcode scanning, batch/serial tracking, supplier approvals, partial receipts, CSV imports, reorder suggestions, audit exports, webhook notifications, and role-specific permissions.

## License

This product follows the repository's MIT license.
