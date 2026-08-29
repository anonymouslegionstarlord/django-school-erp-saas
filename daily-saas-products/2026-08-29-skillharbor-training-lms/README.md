# SkillHarbor — Django Employee Training LMS SaaS

SkillHarbor is a portfolio-ready, multi-tenant employee training and compliance platform built with Python and Django. Learning teams author structured courses, assign them with due dates, follow module-level progress, record final scores, and monitor completion from one responsive workspace.

![Django](https://img.shields.io/badge/Django-5.2_LTS-0c4b33?logo=django)
![Python](https://img.shields.io/badge/Python-3.12-3776ab?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-ready-4169e1?logo=postgresql&logoColor=white)
![Coverage](https://img.shields.io/badge/test_coverage-92%25-315c43)

## Product capabilities

- Isolated organization workspaces with owner, learning manager, instructor, and learner roles
- Self-service workspace registration with an editable starter course and module
- Course catalog with codes, categories, levels, instructors, duration, pass marks, and mandatory flags
- Ordered learning modules with lesson content, duration, and optional resource links
- Draft, published, and archived course lifecycle
- Publication gate requiring at least one module
- Learner assignments with due dates and automatic module-level progress scope
- Assigned, in-progress, and completed enrollment workflow
- Learner notes and auditable assignment activity
- Automatic overdue detection for unfinished learning
- Final-score gate that requires every module and the configured pass mark
- Immutable completed enrollments
- Role-aware dashboards for learning operations and personal development
- Completion, mandatory-compliance, overdue, and average-score metrics
- Searchable and filterable course and assignment views
- Tenant-scoped JSON APIs for reporting and integrations
- Responsive server-rendered frontend with no JavaScript build step
- Repeatable realistic sample data
- SQLite for a zero-configuration first run and PostgreSQL for Docker/production
- Secure production settings, WhiteNoise, Gunicorn, Docker, Render, and GitHub Actions support

## Technology

| Layer | Choice |
|---|---|
| Backend | Python 3.12, Django 5.2 LTS |
| Frontend | Django templates and custom responsive CSS |
| Authentication | Django sessions and password validators |
| API | Authenticated, read-only Django JSON views |
| Database | SQLite locally; PostgreSQL in Docker and production |
| Production | Gunicorn and WhiteNoise |
| Quality | Django TestCase, Coverage, Ruff, GitHub Actions |

## First-time setup — Windows

These commands use PowerShell on Windows 10 or 11.

### 1. Install prerequisites

Install [Python 3.12](https://www.python.org/downloads/) and [Git](https://git-scm.com/download/win). During Python installation, select **Add Python to PATH**.

### 2. Clone and enter SkillHarbor

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-29-skillharbor-training-lms
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
pip install -r requirements-dev.txt
```

### 5. Configure and initialize

```powershell
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
```

The local defaults work without editing `.env`. Never use its example secret in production.

### 6. Start the server

```powershell
python manage.py runserver
```

Open <http://127.0.0.1:8000>.

## First-time setup — macOS or Linux

Install Python 3.12 and Git, then run:

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-08-29-skillharbor-training-lms
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

If `python3.12` is unavailable but `python3 --version` reports 3.12 or newer, use `python3` when creating the virtual environment.

## Demo accounts

Run `python manage.py seed_demo`. All four accounts use `DemoPass123!`:

| Role | Username | Useful workflow |
|---|---|---|
| Owner | `demo_learning` | View organization learning health and manage all content |
| Learning manager | `demo_lnd_manager` | Author courses, assign learning, and grade any learner |
| Instructor | `demo_instructor` | Maintain assigned courses, track learners, and record scores |
| Learner | `demo_learner` | Complete assigned modules, add notes, and review results |

The command is idempotent and resets these demo passwords. It is intended only for local or disposable demonstration databases.

The sample workspace contains:

- Four courses across security, customer success, leadership, and responsible AI
- Eleven substantive learning modules
- One in-progress mandatory assignment
- One passed and completed assignment
- One overdue leadership assignment
- Activity and learner-note history

## Run with Docker and PostgreSQL

Install Docker Desktop, enter this project directory, then run:

```bash
docker compose up --build
```

The web container waits for PostgreSQL, applies migrations, creates demo data, and starts Gunicorn. Open <http://localhost:8000>.

Useful Docker commands:

```bash
# Follow application logs
docker compose logs -f web

# Run Django checks
docker compose exec web python manage.py check

# Open a Django shell
docker compose exec web python manage.py shell

# Stop while preserving PostgreSQL data
docker compose down

# Stop and delete the local PostgreSQL volume
docker compose down -v
```

## Learning workflow and permissions

```text
Owner / manager / instructor: draft course → add modules → publish
                                                      ↓
Owner / manager / instructor: assign learner + due date
                                                      ↓
Learner: assigned → complete first module → in progress
                                                      ↓
Instructor / manager: all modules + passing score → completed
```

| Capability | Owner | Learning manager | Instructor | Learner |
|---|:---:|:---:|:---:|:---:|
| View organization learning data | Yes | Yes | Own courses | Own assignments |
| Create courses and modules | Yes | Yes | Yes | No |
| Edit any course | Yes | Yes | No | No |
| Edit an assigned course | Yes | Yes | Yes | No |
| Assign any published course | Yes | Yes | No | No |
| Assign an instructed course | Yes | Yes | Yes | No |
| Update module progress | Yes | Yes | Own courses | Own assignments |
| Record final scores | Yes | Yes | Own courses | No |
| Read another tenant's data | No | No | No | No |

Instructors may browse published organization courses but can modify and deliver only courses assigned to them. Learners see only published courses connected to their assignments. Every cross-tenant object lookup returns `404`.

## Completion and compliance rules

SkillHarbor enforces learning outcomes on the server:

1. A course cannot be published without at least one module.
2. Only published courses can be assigned.
3. Each learner can have only one active record for the same course.
4. An assignment receives one progress record for every course module.
5. Completing the first module moves an assignment from **Assigned** to **In progress**.
6. A final score cannot be recorded until every module is complete.
7. A score below the course pass mark requires instructor feedback and keeps the assignment in progress.
8. A passing score completes and freezes the enrollment.
9. Unfinished assignments past their due date are reported as overdue.

The completion rate is completed assignments divided by all visible assignments. Mandatory compliance measures completed assignments for mandatory courses. Learner progress is completed modules divided by total course modules.

## JSON API

Sign in through the web application first, then use:

| Endpoint | Purpose |
|---|---|
| `/api/summary/` | Role-aware course, enrollment, overdue, score, and completion metrics |
| `/api/courses/` | Visible course catalog; accepts `?category=compliance` |
| `/api/enrollments/` | Visible assignments; accepts `?status=in_progress` |
| `/api/enrollments/<id>/` | One assignment with module progress and learner notes |

Example after signing in through a browser:

```bash
curl --cookie "sessionid=YOUR_SESSION_COOKIE" http://127.0.0.1:8000/api/enrollments/
```

API querysets begin with the authenticated membership and organization. The learner and instructor scopes are applied before serialization. These endpoints are intentionally read-only in the MVP; browser workflows own validated progress, grading, and activity transitions.

## Environment variables

| Variable | Production | Purpose |
|---|:---:|---|
| `DJANGO_SECRET_KEY` | Required | Long, unique random signing secret |
| `DJANGO_DEBUG` | Required | Set to `False` |
| `DJANGO_ALLOWED_HOSTS` | Required | Comma-separated deployment hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Required for HTTPS forms | Origins including `https://` |
| `DATABASE_URL` | Recommended | PostgreSQL connection URL |
| `DJANGO_TIME_ZONE` | Optional | Defaults to `Asia/Kolkata` |
| `DJANGO_SECURE_SSL_REDIRECT` | Optional | Defaults to `True` when debug is off |

When `DATABASE_URL` is unset, Django uses a local `db.sqlite3`, which is ignored by Git.

## Common commands

Run these from the SkillHarbor directory with the virtual environment active:

```bash
# Migrate and load or refresh sample data
python manage.py migrate
python manage.py seed_demo

# Create a production administrator
python manage.py createsuperuser

# Development and production configuration checks
python manage.py check
DJANGO_DEBUG=False DJANGO_SECRET_KEY=test-only-8Qv4mZ7pR2xN9cL5wT1hK6sF3aJ0uY4eB8dG2nM7iP5rS9 \
  DJANGO_ALLOWED_HOSTS=example.com \
  DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com \
  python manage.py check --deploy

# Detect missing migrations
python manage.py makemigrations --check --dry-run

# Format, lint, and test
ruff format --check .
ruff check .
coverage run manage.py test
coverage report --fail-under=88

# Production static assets
DJANGO_DEBUG=False DJANGO_SECRET_KEY=test-only-8Qv4mZ7pR2xN9cL5wT1hK6sF3aJ0uY4eB8dG2nM7iP5rS9 \
  DJANGO_ALLOWED_HOSTS=example.com python manage.py collectstatic --noinput
```

## Architecture

```text
2026-08-29-skillharbor-training-lms/
├── config/                       # Settings, root URLs, ASGI, and WSGI
├── learning/
│   ├── management/commands/seed_demo.py
│   ├── migrations/              # Versioned database schema
│   ├── static/learning/app.css  # Responsive visual system
│   ├── models.py                # Tenancy, courses, progress, and activity
│   ├── forms.py                 # Scoped forms and completion validation
│   ├── views.py                 # Role-aware workflows and JSON APIs
│   └── tests.py                 # Isolation, permission, lifecycle, and API tests
├── templates/                   # Landing, authentication, courses, assignments
├── Dockerfile
├── docker-compose.yml
└── render.yaml
```

`Organization` is the tenant boundary. Each user has one `Membership`, and every business record carries an organization foreign key. Views resolve the membership before querying, relational form choices are scoped to the organization and role, object lookups include the tenant, and model validation rejects cross-organization relationships.

`Course` owns ordered `Module` records. Assigning a course creates an `Enrollment` and one `LessonProgress` record per module inside a database transaction. `Activity` provides a compact append-only timeline for assignment, completion, scoring, and coaching context.

## Secure defaults

- CSRF middleware protects state-changing forms.
- Session and CSRF cookies become secure when debug is disabled.
- Production mode enables HTTPS redirect, HSTS, proxy SSL handling, content-type sniffing protection, and clickjacking denial.
- Passwords use Django's hashing and validator stack.
- Course publication, progress updates, and grading require POST plus explicit authorization.
- Form querysets and model validation independently protect tenant relationships.
- Score and completion gates run on the server.
- Completed enrollments are immutable.
- `.env`, databases, virtual environments, coverage files, caches, collected static assets, and media are ignored.
- The local fallback secret is deliberately marked insecure and must be replaced in production.

For a larger production platform, add invitation or SSO provisioning, SCORM/xAPI content, assessment question banks, signed certificates, email reminders, background jobs, object storage, audit export, API tokens, rate limiting, observability, and database backups.

## Deploy to Render

The included `render.yaml` is a reference blueprint. For this monorepo, create a Render web service from the GitHub repository and set **Root Directory** to:

```text
daily-saas-products/2026-08-29-skillharbor-training-lms
```

Then configure:

```text
Build command: pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
Start command: gunicorn config.wsgi:application
```

Attach managed PostgreSQL as `DATABASE_URL`, generate a long `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=False`, and configure the exact host and HTTPS origin in `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`. Do not run `seed_demo` against a real production database.

Before launch, run the test suite and deployment check, replace demo provisioning with invitations or SSO, enable backups and monitoring, and review training-data retention requirements.

## License

This project inherits the repository's MIT License.
