# ClauseTrack — Contract Lifecycle SaaS

ClauseTrack is a portfolio-ready, multi-tenant Django SaaS for legal and operations teams. It replaces contract spreadsheets with a searchable agreement register, renewal radar, obligation ownership, and an auditable activity trail.

## Functional MVP

- Self-service authentication and isolated organization workspaces
- Owner, legal manager, and read-only viewer roles
- Counterparty directory and searchable contract portfolio
- Agreement type, value, term, notice window, renewal, status, and ownership
- Renewal/expiry attention dashboard and active portfolio value
- Assignable obligations with overdue detection and completion audit events
- Contract notes and chronological activity trail
- Tenant-scoped JSON APIs at `/api/summary/`, `/api/contracts/`, and `/api/obligations/`
- Responsive frontend, SQLite/PostgreSQL support, Docker, Render blueprint, tests, and demo data

## Demo accounts

All use password `DemoPass123!`:

| Role | Username |
|---|---|
| Owner | `demo_contracts` |
| Legal manager | `demo_legal` |
| Viewer | `demo_viewer` |

## First-time setup — Windows PowerShell

Install Python 3.12 and Git, then:

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-25-clausetrack-contracts
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

If activation is blocked, first run `Set-ExecutionPolicy -Scope Process Bypass`. Open <http://127.0.0.1:8000>.

## First-time setup — macOS or Linux

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-08-25-clausetrack-contracts
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

## Docker setup

With Docker Desktop or Docker Engine + Compose installed:

```bash
docker compose up --build
```

The web container waits for PostgreSQL, applies migrations, seeds the demo, and serves at <http://localhost:8000>. Stop with `docker compose down`; add `-v` only when you intentionally want to erase the database volume.

## Common commands

```bash
python manage.py seed_demo
python manage.py createsuperuser
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test
pip install -r requirements-dev.txt
ruff format --check .
ruff check .
coverage run manage.py test && coverage report
```

## Architecture and isolation

`Organization` is the tenant boundary, with one `Membership` per user. Contracts, counterparties, obligations, and activities each carry an organization key. The `workspace_required` decorator resolves the authenticated membership, and every web/API queryset filters on that organization. Form querysets restrict foreign keys to members and counterparties in the same workspace. Manager-only mutations are enforced server-side; UI hiding is only convenience. Database uniqueness constraints protect references and counterparty emails per tenant.

The project uses Django templates and custom responsive CSS, Django's session authentication, WhiteNoise for static assets, Gunicorn for serving, SQLite for zero-config local use, and PostgreSQL through `DATABASE_URL` in containers and production.

## Environment and secure defaults

Copy `.env.example` for a reference, then export values or use your hosting provider's environment settings. Django does not load `.env` automatically, which avoids surprising production behavior. Never commit `.env`.

In production set a strong unique `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, the exact `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain`, and a managed PostgreSQL `DATABASE_URL`. Production mode enables HTTPS redirects, secure cookies, HSTS, clickjacking protection, content-type sniffing protection, and hashed static manifests.

## Deploy to Render

1. Push this repository to GitHub and create a Render Blueprint from this folder's `render.yaml`.
2. Update the hostname and trusted origin in `render.yaml` if Render assigns a different service name.
3. Deploy. The blueprint provisions PostgreSQL, installs dependencies, collects static files, migrates, and starts Gunicorn.
4. Open a Render shell and run `python manage.py createsuperuser` (recommended) or `python manage.py seed_demo` only for a public demo.

For another platform, run `pip install -r requirements.txt`, `python manage.py collectstatic --noinput`, `python manage.py migrate`, then `gunicorn config.wsgi:application`. Use managed HTTPS and PostgreSQL, rotate secrets, restrict hosts/origins, back up the database, and run migrations as a release step.
