# ClassOrbit — Django School ERP SaaS

A portfolio-ready, multi-tenant School ERP built with Python and Django. Each school gets an isolated workspace for students, teachers, courses, attendance, fee invoices, and payments, plus a tenant-scoped REST API.

## Daily SaaS portfolio

The School ERP remains the repository's root application. Independent full-stack products are stored under `daily-saas-products/`:

| Date | Product | Domain | Setup |
|---|---|---|---|
| 2026-08-17 | ClientFlow | Multi-tenant sales CRM | [`daily-saas-products/2026-08-17-clientflow-crm/README.md`](daily-saas-products/2026-08-17-clientflow-crm/README.md) |

![Django](https://img.shields.io/badge/Django-5.2_LTS-0c4b33?logo=django)
![Python](https://img.shields.io/badge/Python-3.12-3776ab?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-ready-4169e1?logo=postgresql&logoColor=white)
![CI](https://github.com/anonymouslegionstarlord/django-school-erp-saas/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-6c5ce7)

## What it includes

- Multi-school SaaS tenancy with every web and API query scoped to the active school
- Owner, administrator, teacher, and accountant membership roles
- Self-service school registration and secure Django authentication
- Student and guardian directory
- Teacher and course management
- Daily attendance register
- Fee invoices, partial/full payments, balances, and overdue status
- Responsive operations dashboard
- REST API with session and basic authentication
- PostgreSQL and SQLite support
- Repeatable demo-data command
- Docker Compose development environment
- Render deployment blueprint
- GitHub Actions checks, tests, coverage, and linting

## Technology

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Django 5.2 LTS |
| Frontend | Django Templates, responsive CSS |
| API | Django REST Framework |
| Database | SQLite locally, PostgreSQL in Docker/production |
| Static files | WhiteNoise |
| Production server | Gunicorn |
| Quality | Django TestCase, DRF APIClient, Ruff, Coverage |

## First-time setup — Windows

These steps work in PowerShell on Windows 10 or 11.

### 1. Install prerequisites

Install:

- [Python 3.12](https://www.python.org/downloads/)
- [Git](https://git-scm.com/download/win)

During Python installation, select **Add Python to PATH**.

### 2. Clone and enter the project

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas
```

### 3. Create and activate a virtual environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this once in the same terminal and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 4. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configure the environment

```powershell
Copy-Item .env.example .env
```

The project uses safe local defaults, so `.env` is optional for your first run. Never commit a real secret key.

### 6. Prepare the database and demo account

```powershell
python manage.py migrate
python manage.py seed_demo
```

### 7. Start the server

```powershell
python manage.py runserver
```

Open <http://127.0.0.1:8000>.

## First-time setup — macOS or Linux

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas
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

Run `python manage.py seed_demo`, then sign in with:

```text
Username: demo_admin
Password: DemoPass123!
```

This credential is for local demonstration only. The command resets the demo password each time it runs; do not run it against a real production database.

You can also select **Start free** on the landing page to create a separate school and owner account.

## Run with Docker

Install Docker Desktop, then run:

```bash
docker compose up --build
```

In a second terminal, add sample records:

```bash
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000>. Docker uses PostgreSQL and keeps data in the `postgres_data` volume.

To stop the containers without deleting data:

```bash
docker compose down
```

## Environment variables

| Variable | Required in production | Example/purpose |
|---|---:|---|
| `DJANGO_SECRET_KEY` | Yes | Long random secret |
| `DJANGO_DEBUG` | Yes | `False` in production |
| `DJANGO_ALLOWED_HOSTS` | Yes | `your-app.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | For HTTPS forms | `https://your-app.onrender.com` |
| `DJANGO_SECURE_SSL_REDIRECT` | No | Defaults to `True` in production |
| `DATABASE_URL` | Recommended | PostgreSQL connection URL |
| `DJANGO_TIME_ZONE` | No | Defaults to `Asia/Kolkata` |

If `DATABASE_URL` is empty, Django uses `db.sqlite3` locally.

## Useful commands

```bash
# Create a real admin account
python manage.py createsuperuser

# Verify configuration
python manage.py check

# Run all tests
python manage.py test

# Run linting
ruff check .

# Run coverage locally
coverage run manage.py test
coverage report

# Create migrations after changing models
python manage.py makemigrations
python manage.py migrate
```

## REST API

Sign in through the web application, then visit:

| Endpoint | Purpose |
|---|---|
| `/api/students/` | List and manage students |
| `/api/teachers/` | List and manage teachers |
| `/api/courses/` | List and manage courses |
| `/api/invoices/` | List and manage invoices |

Example with local basic authentication:

```bash
curl -u demo_admin:DemoPass123! http://127.0.0.1:8000/api/students/
```

API querysets are filtered by the authenticated user’s active school. Write access follows role permissions.

## Project structure

```text
django-school-erp-saas/
├── config/                 # Django settings and root URLs
├── core/                   # Tenant models, views, forms, API, tests
│   ├── management/commands/seed_demo.py
│   └── migrations/
├── templates/              # Landing, auth, dashboard, ERP screens
├── static/core/            # Responsive application styles
├── .github/workflows/      # CI pipeline
├── Dockerfile
├── docker-compose.yml
├── render.yaml
└── manage.py
```

## SaaS tenancy design

`Membership` connects a Django user to a `School` with a role. `ActiveSchoolMiddleware` resolves the signed-in user's active membership and attaches `request.school` and `request.membership`. Every page and API view filters records by `request.school`; submitted foreign keys are also validated to prevent cross-school access.

For a larger production system, good next steps are:

- PostgreSQL row-level security or schema-based isolation
- invitation emails and multi-school switcher
- object-level audit log
- asynchronous jobs with Celery/Redis
- payment gateway webhooks
- rate limiting and API tokens
- automated backups and observability

## Deploy to Render

The included `render.yaml` creates the web service and PostgreSQL database.

1. Push the repository to GitHub.
2. In Render, choose **New → Blueprint**.
3. Select this repository and apply `render.yaml`.
4. After the first deploy, set `DJANGO_CSRF_TRUSTED_ORIGINS` to the full HTTPS Render URL.
5. Open a Render shell and run `python manage.py createsuperuser`.

Do not run `seed_demo` in production.

## Troubleshooting

### `python` or `py` is not recognized

Reinstall Python and enable **Add Python to PATH**, then reopen the terminal.

### `No module named django`

Activate `.venv`, then run `pip install -r requirements.txt`.

### `no such table`

Run `python manage.py migrate`.

### Port 8000 is already in use

Use another port:

```bash
python manage.py runserver 8001
```

### PostgreSQL connection error in Docker

Wait for the database health check, then run:

```bash
docker compose restart web
```

## License

Released under the [MIT License](LICENSE).
