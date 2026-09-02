# ReturnRelay — Returns and Warranty Operations SaaS

ReturnRelay is a portfolio-ready, multi-tenant return merchandise authorization (RMA) and warranty-operations product built with Python and Django. It gives product and service teams one workspace for registered warranties, claim decisions, returned-item inspections, resolutions, customer tracking, and auditable status history.

## Product highlights

- Isolated organization workspaces with owner, claims manager, technician, and viewer roles
- Customer, product, serial-number, order-reference, and warranty registration
- Calendar-accurate warranty expiry and eligibility checks
- Return intake with issue evidence, requested remedy, priority, and response SLA
- Guarded lifecycle: submitted → triage → approved/rejected → awaiting item → received → inspecting → resolved → closed
- Technical inspections with condition, fault confirmation, findings, and recommendation
- Repair, replacement, refund, store-credit, and no-fault resolution records
- Refund and credit exposure, overdue response, and inspection-queue reporting
- Customer tracking pages that show only approved updates and hide private operational data
- Tenant-scoped JSON reporting and status-transition APIs
- Responsive interface, SQLite/PostgreSQL support, Docker, WhiteNoise, Gunicorn, and Render
- Repeatable sample workspace and 63 automated tests with a 96% coverage baseline

## Technology

| Layer | Choice |
|---|---|
| Backend | Python 3.12, Django 5.2 LTS |
| Frontend | Server-rendered Django templates and responsive custom CSS |
| Data | SQLite for local use; PostgreSQL for Docker and production |
| API | Authenticated Django JSON endpoints |
| Static files | WhiteNoise compressed manifest storage in production |
| Production server | Gunicorn |
| Quality | Django TestCase, Ruff, Coverage, migration and deployment checks |

## First-time setup on Windows

These commands use PowerShell on Windows 10 or 11.

1. Install [Python 3.12](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win). Select **Add Python to PATH** during Python installation.
2. Clone the repository and enter ReturnRelay:

   ```powershell
   git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
   cd django-school-erp-saas\daily-saas-products\2026-09-02-returnrelay-rma
   ```

3. Create and activate an isolated environment:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If activation is blocked, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` once in that terminal, then activate again.

4. Install, migrate, seed, and run:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py seed_demo
   python manage.py runserver
   ```

5. Open <http://127.0.0.1:8000> and sign in with a demo account below.

## First-time setup on macOS or Linux

Install Python 3.12 and Git, then run:

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-09-02-returnrelay-rma
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open <http://127.0.0.1:8000>.

The application has safe local defaults and uses SQLite when `DATABASE_URL` is absent. `.env.example` documents every setting; export those variables in your shell or configure them in your hosting provider. Never commit a real secret or `.env` file.

## Demo accounts

Run `python manage.py seed_demo` first. All accounts use `DemoPass123!`.

| Role | Username | What to try |
|---|---|---|
| Owner | `demo_returns` | Full workspace and returns operations |
| Claims manager | `demo_claims` | Triage, approve, reject, resolve, and close claims |
| Technician | `demo_technician` | Inspect received products and record findings |
| Viewer | `demo_returns_viewer` | Read-only dashboard, catalog, and claim history |

The seed command is idempotent and resets these passwords. It is intended only for local demonstrations—do not run it against production data.

## Run with Docker and PostgreSQL

From this product directory:

```bash
docker compose up --build -d
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000>. The web container runs migrations when it starts, while PostgreSQL data persists in the `returnrelay_postgres` volume.

```bash
# View logs
docker compose logs -f web

# Stop without deleting data
docker compose down

# Stop and delete the local PostgreSQL volume
docker compose down -v
```

## Roles and permissions

| Capability | Owner | Claims manager | Technician | Viewer |
|---|:---:|:---:|:---:|:---:|
| View tenant dashboard, claims, customers, catalog, and team | ✓ | ✓ | ✓ | ✓ |
| Add customers, products, registered items, and claims | ✓ | ✓ | — | — |
| Make claim decisions and advance claim status | ✓ | ✓ | — | — |
| Record or update item inspections | ✓ | ✓ | ✓ | — |
| Add workspace members | ✓ | ✓ | — | — |

Every interface and API query is constrained to the signed-in member's organization. Forms restrict selectable relationships, and models independently reject cross-tenant references.

## RMA workflow rules

ReturnRelay enforces these rules in transactional services and model validation, not only in the browser:

- A claim can move only through the documented lifecycle; invalid skips and terminal-state changes are rejected.
- Only an owner or claims manager can approve, reject, resolve, close, or otherwise change claim status.
- Rejection requires a reason and timestamp.
- A received item must have an inspection before the claim can be resolved.
- A technician, claims manager, or owner can record an inspection; viewers cannot.
- A refund or store credit requires a positive monetary value.
- A replacement requires a fulfillment reference.
- A resolved claim requires a resolution type, summary, and timestamp.
- Closing requires an existing resolution and records the close timestamp.
- Every status transition and inspection writes an actor-attributed audit event.
- Each event independently controls whether it is visible on public customer tracking.

Response targets are four hours for urgent claims, 24 hours for high, 48 hours for normal, and 72 hours for low priority. These are demonstration business defaults and can be changed in `returns/services.py`.

## JSON API

The API uses the same authenticated Django session and role rules as the interface.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/summary/` | Tenant-scoped workflow, overdue, and inspection counts |
| `GET` | `/api/v1/claims/` | Up to 100 tenant claims with coverage and SLA flags |
| `GET` | `/api/v1/claims/?status=received` | Filter claims by a valid status |
| `GET` | `/api/v1/catalog/` | Tenant product and warranty configuration |
| `POST` | `/api/v1/claims/<id>/transition/` | Advance a permitted claim using JSON |

Example status update body:

```json
{
  "status": "approved",
  "message": "Warranty coverage confirmed; return instructions sent.",
  "visible_to_customer": true
}
```

Example resolution body:

```json
{
  "status": "resolved",
  "message": "Replacement dispatched to the registered customer.",
  "resolution": "replaced",
  "resolution_summary": "Unit replaced after a confirmed controller fault.",
  "replacement_reference": "SHIP-RPL-1048",
  "visible_to_customer": true
}
```

Browser POST requests require Django's CSRF token. For a production mobile or partner integration, add dedicated token or OAuth authentication rather than disabling CSRF.

## Architecture

```text
Browser / customer tracking / JSON client
                    │
       Django views and role decorators
                    │
       Transactional RMA services
                    │
 Tenant-validating models and constraints
                    │
       SQLite locally / PostgreSQL live
```

`Membership` binds one authenticated user to one `Organization`. Business records carry an explicit organization foreign key. Query scoping protects reads, forms constrain selectable relations, models reject tenant mismatches, and transactional services lock claims while changing their status or inspection.

Key files:

- `returns/models.py` — tenant data, warranty calculations, constraints, and validation
- `returns/services.py` — SLA rules, tracking codes, inspections, and atomic transitions
- `returns/decorators.py` — workspace, manager, and inspector authorization
- `returns/views.py` — web workflows, privacy-aware tracking, and JSON endpoints
- `returns/management/commands/seed_demo.py` — repeatable portfolio sample data
- `returns/tests.py` — permission, isolation, workflow, API, form, and UI tests
- `returns/static/returns/app.css` — responsive navy-and-coral visual system

## Environment variables

| Variable | Production | Purpose |
|---|---:|---|
| `DJANGO_SECRET_KEY` | Required | Long, random signing key |
| `DJANGO_DEBUG` | Set to `False` | Enables production security and static storage |
| `DJANGO_ALLOWED_HOSTS` | Required | Comma-separated hostnames, without schemes |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Required for HTTPS forms | Comma-separated origins including `https://` |
| `DATABASE_URL` | Recommended | PostgreSQL connection URL; absent means local SQLite |
| `DJANGO_TIME_ZONE` | Optional | Defaults to `Asia/Kolkata` |
| `DJANGO_SECURE_SSL_REDIRECT` | Optional | Defaults to `True` when debug is off |

Generate a secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Common development commands

```bash
# Create or refresh local sample data
python manage.py seed_demo

# Create an administrator
python manage.py createsuperuser

# Check configuration and migrations
python manage.py check
python manage.py makemigrations --check --dry-run

# Run the quality suite
pip install -r requirements-dev.txt
ruff format --check .
ruff check .
coverage run manage.py test
coverage report

# Prepare static assets exactly as production does
DJANGO_DEBUG=False DJANGO_SECRET_KEY=local-check \
DJANGO_ALLOWED_HOSTS=localhost python manage.py collectstatic --noinput
```

## Deploy on Render

1. Push or fork the repository into your GitHub account.
2. In Render, create a **Blueprint** and select this repository.
3. Point the Blueprint at `daily-saas-products/2026-09-02-returnrelay-rma/render.yaml`.
4. After Render assigns the service hostname, set:
   - `DJANGO_ALLOWED_HOSTS` to that hostname, such as `returnrelay.onrender.com`.
   - `DJANGO_CSRF_TRUSTED_ORIGINS` to its full HTTPS origin, such as `https://returnrelay.onrender.com`.
5. Deploy. The blueprint provisions PostgreSQL, collects static files, runs migrations, and starts Gunicorn.
6. Open a Render shell and run `python manage.py createsuperuser` for the first production administrator. Create real users through a controlled invitation flow; do not seed demonstration records in a live environment.

For other platforms, use the build and start commands shown in `render.yaml`. Terminate TLS at the platform proxy and keep `DJANGO_DEBUG=False`.

## Security defaults

- HTTP-only session and CSRF cookies
- Secure cookies, HTTPS redirect, proxy SSL handling, and one-year HSTS when debug is off
- Denied iframe embedding and content-type sniffing
- Django password validation for signup and workspace-member creation
- CSRF protection on HTML and JSON mutations
- Tenant scoping at query, form, model, and service layers
- Public tracking excludes email, phone, serial number, evidence URL, and internal events
- Cryptographically random, tenant-unique public tracking codes
- No committed secrets, databases, environments, coverage files, or generated assets

Public tracking codes are privacy-aware identifiers, not authentication credentials. For highly sensitive products, add customer verification, rate limiting, and expiration before exposing tracking outside a trusted customer portal.

## MVP boundaries

ReturnRelay intentionally does not pretend to include courier-label purchasing, warehouse barcode scans, file uploads, payment-gateway refunds, email/SMS delivery, or ERP/e-commerce synchronization. Those are clear production integrations; the current MVP fully implements the tenancy, eligibility, decision, inspection, resolution, audit, API, and customer-visibility workflows described above.

## License

This project is covered by the repository's MIT license.
