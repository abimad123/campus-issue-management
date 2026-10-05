# LPU Campus Issue Management & Network Quality Analytics Platform

An academic project foundation for campus service requests, maintenance coordination, and network quality monitoring in a realistic university setting. It uses Lovely Professional University as project context and does not claim official affiliation or operation by LPU.

This repository is currently at **Phase 1: Foundation**. The application shell and service infrastructure exist; issue workflows, authentication, operational data, and analytics are not implemented. Dashboard values are intentionally blank until backed by real records.

## Technology

- Backend: Python 3.12, Django 5, Django REST Framework, PostgreSQL
- Frontend: React 18, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query
- Background services: Celery, Celery Beat, Redis
- Development infrastructure: Docker Compose

## Structure

    backend/config/          Django settings, URLs, ASGI/WSGI, Celery
    backend/apps/            Core API and domain-oriented Django app boundaries
    frontend/src/components/ Small reusable UI primitives
    frontend/src/lib/         API request abstraction
    docs/                    Architecture and domain direction
    compose.yaml              Local multi-service environment

Backend domain apps are intentionally empty boundaries at this stage. See [docs/architecture.md](docs/architecture.md) for ownership and future direction.

## Local setup

Requirements: Python 3.12+, Node.js 20+, npm, and PostgreSQL 16. Redis is required for Celery.

1. Copy `.env.example` to `.env` and set a private development secret and database password. Never commit `.env`.
2. Create and activate a Python virtual environment, then install backend requirements:

       cd backend
       python -m venv .venv
       .venv\Scripts\Activate.ps1
       pip install -r requirements.txt
       python manage.py migrate
       python manage.py runserver

3. In another terminal, install and start the frontend:

       cd frontend
       npm install
       npm run dev

The UI is at `http://localhost:5173`; the API liveness endpoint is `http://localhost:8000/api/health/`. The endpoint reports that the Django process is alive; it does not check database readiness.

### Celery

With Redis running and backend dependencies installed, start the worker and Beat scheduler in separate terminals:

       cd backend
       celery -A config worker --loglevel=info

       cd backend
       celery -A config beat --loglevel=info

`apps.core.tasks.debug_task` is an infrastructure smoke task. No periodic business tasks are scheduled in Phase 1.

## Docker setup

From the repository root, create `.env` from `.env.example` and replace the sample credentials. Then run:

       docker compose up --build

Services are exposed at frontend `http://localhost:5173` and API `http://localhost:8000`. PostgreSQL data persists in a named volume; Redis uses its default ephemeral development configuration. To stop services, run `docker compose down`. To remove persisted local database data, explicitly run `docker compose down -v`.

## Configuration

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django signing key; use a private random value |
| `DJANGO_DEBUG` | Enables development diagnostics when `true` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated Django host allowlist |
| `DJANGO_CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins allowed by the API |
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Local database password |
| `POSTGRES_HOST` / `POSTGRES_PORT` | Database connection target; Compose overrides host to `postgres` |
| `REDIS_URL` | Celery broker and result backend URL; Compose overrides host to `redis` |
| `VITE_API_BASE_URL` | API root used by the browser frontend |

## Checks and tests

       cd backend
       python manage.py check
       python manage.py test
       cd ..\frontend
       npm run lint
       npm run build
       cd ..
       docker compose config --quiet

The Docker command validates Compose configuration. To verify running services, start Compose and request `/api/health/` in a browser or with `curl`.
