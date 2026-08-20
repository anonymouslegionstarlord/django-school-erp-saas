# SprintBoard — Multi-tenant Project Management SaaS

SprintBoard is a full-stack Django project-delivery platform for small teams. Every organization gets an isolated workspace for projects, Kanban tasks, assignees, priorities, due dates, comments, and delivery metrics.

## Functional MVP

- Atomic signup creates an owner and team workspace
- Projects with codes, descriptions, colors, and progress counts
- Five-column Kanban workflow: backlog, to do, in progress, review, done
- Task priorities, due dates, assignees, comments, overdue detection, and filtering
- Dashboard for active, completed, overdue, assigned, and recently updated work
- Tenant-scoped summary, projects, and tasks JSON APIs
- Responsive frontend, repeatable demo data, SQLite/PostgreSQL, Docker, Render, and secure defaults
- 15 automated tests emphasizing cross-tenant isolation and workflows

## First-time setup — Windows

Install Python 3.12 and Git, then use PowerShell:

```powershell
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas\daily-saas-products\2026-08-20-sprintboard-projects
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. Open <http://127.0.0.1:8000>.

## First-time setup — macOS or Linux

```bash
git clone https://github.com/anonymouslegionstarlord/django-school-erp-saas.git
cd django-school-erp-saas/daily-saas-products/2026-08-20-sprintboard-projects
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
Username: demo_lead
Password: DemoPass123!
```

Run `python manage.py seed_demo` first. It resets the demo workspace and password; never run it against production.

## Docker

```bash
docker compose up --build
docker compose exec web python manage.py seed_demo
```

Open <http://localhost:8000>. Stop with `docker compose down`.

## Environment variables

| Variable | Production use |
|---|---|
| `DJANGO_SECRET_KEY` | Required long random secret |
| `DJANGO_DEBUG` | Set to `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts |
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

## API endpoints

After browser sign-in:

- `GET /api/v1/summary/`
- `GET /api/v1/projects/`
- `GET /api/v1/tasks/`

All results are limited to the signed-in organization.

## Architecture

```text
User ──1 Membership *──1 Organization
                              ├──* Project ──* Task ──* Comment
                              └──────────────── tenant boundary
```

The organization is resolved from the authenticated membership. Every project, task, comment, form queryset, object lookup, mutation, and API query includes that tenant boundary; foreign IDs return `404`.

## Deployment

Create a Render Blueprint, choose this repository, set its root directory to `daily-saas-products/2026-08-20-sprintboard-projects`, and use `render.yaml`. Configure the final allowed host and CSRF origin, deploy, then run migrations and create a superuser in the Render shell.

Production extensions can add invitations, multiple workspace memberships, activity audit logs, file attachments, sprint planning, notifications, webhooks, drag-and-drop updates, pagination, and token authentication.
