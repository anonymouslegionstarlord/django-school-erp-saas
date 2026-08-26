# TalentNest — Applicant Tracking SaaS

TalentNest is a portfolio-ready, multi-tenant Django SaaS for hiring teams. It replaces disconnected spreadsheets and interview notes with a clear job register, candidate directory, six-stage pipeline, structured interviews, scored feedback, and an auditable activity trail.

## Functional MVP

- Self-service authentication and isolated organization workspaces
- Owner, recruiter, and interviewer roles with server-side authorization
- Job requisitions with department, location, employment type, openings, status, and owner
- Searchable candidate directory with source, company, contact details, and skills
- Applied, screening, interview, offer, hired, and rejected pipeline stages
- Candidate ratings, recruiter summaries, application ownership, and time-in-pipeline metrics
- Interview scheduling with format, duration, interviewer, meeting link, and slot protection
- Assigned-interviewer feedback with required completion score and written assessment
- Hiring dashboard with active jobs, funnel counts, upcoming interviews, and monthly hires
- Tenant-scoped JSON APIs at `/api/summary/`, `/api/jobs/`, `/api/applications/`, and `/api/interviews/`
- Responsive custom frontend, SQLite/PostgreSQL support, Docker, Render configuration, automated tests, and idempotent demo data

## Demo accounts

All demo accounts use password `DemoPass123!`.

| Role | Username | Access |
|---|---|---|
| Owner | `demo_talent` | Full workspace and hiring management |
| Recruiter | `demo_recruiter` | Jobs, candidates, pipeline, and interviews |
| Interviewer | `demo_interviewer` | Assigned interviews, candidate context, and feedback |

## First-time setup — Windows PowerShell

Install Python 3.12 and Git, then run:

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-26-talentnest-ats
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` once in that terminal and activate again. Open <http://127.0.0.1:8000>.

## First-time setup — macOS or Linux

Install Python 3.12 and Git, then run:

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-08-26-talentnest-ats
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open <http://127.0.0.1:8000>. SQLite is used automatically, so PostgreSQL is not required for the first run.

## Docker setup

Install Docker Desktop or Docker Engine with Compose, then run from this project folder:

```bash
docker compose up --build
```

Compose starts PostgreSQL, waits for database health, applies migrations, loads the idempotent demo, and serves TalentNest at <http://localhost:8000>.

```bash
docker compose down
docker compose down -v  # Also erase the local PostgreSQL volume when intentional
```

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
coverage run manage.py test
coverage report
python manage.py collectstatic --noinput
```

`seed_demo` is safe to run repeatedly: it updates the same demo workspace instead of duplicating records.

## Architecture and tenant isolation

`Organization` is the tenant boundary and each user has one `Membership`. `JobOpening`, `Candidate`, `Application`, `Interview`, and `Activity` all carry an organization key. The `workspace_required` decorator resolves the authenticated membership before a protected view runs, and every web and API queryset filters by that organization.

Model forms restrict job, candidate, recruiter, owner, and interviewer choices to the active workspace. Model validation provides a second cross-tenant relation check. Manager mutations are authorized on the server; hiding a button in the frontend is only a convenience. Interviewers can submit feedback only for interviews assigned to them, while owners and recruiters retain management access. Database constraints protect job codes, candidate emails, candidate/job applications, and interviewer time slots.

The project uses Django templates and custom responsive CSS, Django session authentication, WhiteNoise for static assets, Gunicorn for serving, SQLite for zero-configuration local development, and PostgreSQL through `DATABASE_URL` for Docker and production.

## Environment and secure defaults

`.env.example` documents the supported variables. Django intentionally does not auto-load `.env`; export variables in the shell or configure them in your hosting provider. Never commit an actual `.env` file.

| Variable | Local default | Production guidance |
|---|---|---|
| `DJANGO_SECRET_KEY` | Insecure development value | Use a long, unique generated secret |
| `DJANGO_DEBUG` | `True` | Set to `False` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Set exact public hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Empty | Set full HTTPS origins |
| `DJANGO_TIME_ZONE` | `Asia/Kolkata` | Set the hiring team's timezone |
| `DATABASE_URL` | Local SQLite | Use managed PostgreSQL |

Production mode enables HTTPS redirect support, secure cookies, one-year HSTS, clickjacking denial, content-type sniffing protection, and compressed manifest static files. Rotate exposed secrets, enforce HTTPS, restrict hosts and origins, back up PostgreSQL, and run migrations as a controlled release step.

## Deploy to Render

1. Push the repository and create a Render Blueprint using this folder's `render.yaml`.
2. If Render assigns another hostname, update `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to that exact HTTPS domain.
3. Deploy. The blueprint provisions PostgreSQL, installs dependencies, collects static assets, applies migrations, and starts Gunicorn.
4. Open a Render shell and run `python manage.py createsuperuser`. Run `python manage.py seed_demo` only when publishing a portfolio demo.

For another platform, install `requirements.txt`, configure the production variables and PostgreSQL, run `python manage.py collectstatic --noinput`, apply `python manage.py migrate`, and start `gunicorn config.wsgi:application` behind managed HTTPS.

## API examples

The JSON endpoints use the same authenticated Django session and tenant boundary as the web interface:

```bash
curl -b cookies.txt http://127.0.0.1:8000/api/summary/
curl -b cookies.txt http://127.0.0.1:8000/api/jobs/
curl -b cookies.txt http://127.0.0.1:8000/api/applications/
curl -b cookies.txt http://127.0.0.1:8000/api/interviews/
```

They are intentionally read-only in this MVP; web forms own validated state transitions and audit events.
