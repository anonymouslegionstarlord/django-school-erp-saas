# RoutePilot — Fleet Dispatch SaaS

RoutePilot is a portfolio-ready, multi-tenant fleet dispatch and delivery-operations product built with Python and Django. It gives a logistics team one control tower for customer shipments, drivers, vehicles, deadlines, exceptions, and privacy-aware customer tracking.

## Product highlights

- Isolated organization workspaces with owner, dispatcher, driver, and viewer roles
- Shipment intake with customer, pickup, destination, weight, priority, and time windows
- Driver and vehicle assignment with license, availability, capacity, and service checks
- Guarded delivery workflow: assigned → picked up → in transit → delivered or failed
- Required proof reference and delivery note before completion
- Failure reasons, cancellation rules, and immutable status events
- Automatic driver and vehicle release after delivery, failure, or cancellation
- Deadline alerts, urgent queues, fleet utilization, and 30-day on-time reporting
- Customer tracking pages that hide addresses, driver contacts, and internal updates
- Tenant-scoped JSON reporting and transition APIs
- Responsive interface, SQLite/PostgreSQL support, Docker, WhiteNoise, Gunicorn, and Render
- Repeatable demo data and 59 automated tests

## Technology

| Layer | Choice |
|---|---|
| Backend | Python 3.12, Django 5.2 LTS |
| Frontend | Server-rendered Django templates and responsive custom CSS |
| Data | SQLite for local use; PostgreSQL for Docker and production |
| API | Authenticated Django JSON endpoints |
| Static files | WhiteNoise compressed manifest storage in production |
| Production server | Gunicorn |
| Quality | Django TestCase, Ruff, Coverage, Django deployment checks |

## First-time setup on Windows

These commands use PowerShell on Windows 10 or 11.

1. Install [Python 3.12](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win). Select **Add Python to PATH** during Python installation.
2. Clone the repository and enter RoutePilot:

   ```powershell
   git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
   cd django-school-erp-saas\daily-saas-products\2026-09-01-routepilot-fleet-dispatch
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
cd django-school-erp-saas/daily-saas-products/2026-09-01-routepilot-fleet-dispatch
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
| Owner | `demo_routes` | Full operations and workspace access |
| Dispatcher | `demo_dispatcher` | Create, assign, reassign, and cancel shipments |
| Driver | `demo_driver` | Advance the active assigned route |
| Driver | `demo_driver_two` | Available driver ready for another route |
| Viewer | `demo_route_viewer` | Read-only operational visibility |

The seed command is idempotent and resets these passwords. It is intended only for local demonstrations—do not run it against production data.

## Run with Docker and PostgreSQL

From this product directory:

```bash
docker compose up --build -d
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000>. The web container runs migrations when it starts, while PostgreSQL data persists in the `routepilot_postgres` volume.

```bash
# View logs
docker compose logs -f web

# Stop without deleting data
docker compose down

# Stop and delete the local PostgreSQL volume
docker compose down -v
```

## Roles and permissions

| Capability | Owner | Dispatcher | Driver | Viewer |
|---|:---:|:---:|:---:|:---:|
| View workspace dashboard, customers, and fleet | ✓ | ✓ | ✓ | ✓ |
| Create customers, shipments, drivers, and vehicles | ✓ | ✓ | — | — |
| Assign or reassign routes | ✓ | ✓ | — | — |
| Advance any assigned route | ✓ | ✓ | — | — |
| Advance own assigned route | ✓ | ✓ | ✓ | — |
| Cancel a route | ✓ | ✓ | — | — |

Driver shipment queries are narrowed to their own assignments. Every manager and API query is also constrained to the signed-in member's organization.

## Dispatch rules

RoutePilot enforces business rules in the service and model layers, not only in the browser:

- A shipment cannot use a customer, driver, vehicle, actor, or creator from another tenant.
- A driver must have the driver role, a valid license, and `available` status.
- A vehicle must be available, below its next-service odometer, and large enough for the load.
- Assigned routes can move only to `picked_up` or `cancelled`.
- Picked-up routes can move to `in_transit`, `failed`, or `cancelled`.
- In-transit routes can move to `delivered`, `failed`, or `cancelled`.
- Delivery requires both a reference and a proof note; failure requires a reason.
- Drivers can update only their own assignment and cannot cancel it.
- Terminal states release the driver and vehicle for future dispatch.
- Failed shipments can be reassigned through the dispatch workflow.

## JSON API

The API uses the same secure Django session and role rules as the interface.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/summary/` | Tenant-scoped shipment and fleet counts |
| `GET` | `/api/v1/shipments/` | Up to 100 visible shipments |
| `GET` | `/api/v1/shipments/?status=in_transit` | Filter by a valid shipment status |
| `GET` | `/api/v1/fleet/` | Driver and vehicle readiness |
| `POST` | `/api/v1/shipments/<id>/transition/` | Advance a permitted route using JSON |

Example transition body:

```json
{
  "status": "delivered",
  "message": "Delivered at the receiving desk.",
  "delivery_reference": "POD-1048",
  "proof_note": "Signed by Alex at 16:42.",
  "visible_to_customer": true
}
```

Browser POST requests require Django's CSRF token. For a production mobile or partner integration, add a dedicated token/OAuth authentication layer instead of disabling CSRF.

## Architecture

```text
Browser / customer tracking / JSON client
                    │
       Django views and role decorators
                    │
     Transactional dispatch services
                    │
  Tenant-validating models and constraints
                    │
       SQLite locally / PostgreSQL live
```

The `Membership` record binds one authenticated user to one `Organization`. Business records carry an explicit organization foreign key. Query scoping protects reads, forms constrain selectable relations, models reject cross-tenant relations, and transactional services lock shipments while changing assignments or status.

Key files:

- `dispatch/models.py` — tenant-owned data, constraints, and validation
- `dispatch/services.py` — atomic assignment, reassignment, and status transitions
- `dispatch/decorators.py` — workspace and dispatcher authorization
- `dispatch/views.py` — web workflows, public tracking, and JSON endpoints
- `dispatch/management/commands/seed_demo.py` — repeatable portfolio data
- `dispatch/tests.py` — permissions, isolation, workflow, API, and UI tests
- `dispatch/static/dispatch/app.css` — responsive visual system

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
3. Point the Blueprint at `daily-saas-products/2026-09-01-routepilot-fleet-dispatch/render.yaml`.
4. After Render assigns the service hostname, set:
   - `DJANGO_ALLOWED_HOSTS` to that hostname, such as `routepilot.onrender.com`.
   - `DJANGO_CSRF_TRUSTED_ORIGINS` to its full HTTPS origin, such as `https://routepilot.onrender.com`.
5. Deploy. The blueprint provisions PostgreSQL, collects static files, runs migrations, and starts Gunicorn.
6. Open a Render shell and run `python manage.py createsuperuser` for the first production owner. Do not seed the demo workspace in a real environment.

For any other platform, use the same build command and start command shown in `render.yaml`. Terminate TLS at the platform proxy and keep `DJANGO_DEBUG=False`.

## Security defaults

- HTTP-only session and CSRF cookies
- Secure cookies, HTTPS redirect, proxy SSL handling, and one-year HSTS when debug is off
- Denied iframe embedding and content-type sniffing
- Django password validators for sign-up and driver invitations
- CSRF protection on both HTML and JSON mutations
- No public addresses, contact details, or internal shipment events
- No committed secrets, databases, virtual environments, coverage files, or generated assets

## MVP boundaries

RoutePilot intentionally does not pretend to include GPS telemetry, map routing, electronic signatures, notification delivery, or driver background jobs. Those are clear next integrations for a production edition; the current MVP fully implements the dispatch, permission, validation, audit, and customer-visibility workflows described above.

## License

This project is covered by the repository's MIT license.
