# LPU Campus Issue Management & Network Quality Analytics Platform

An academic project for campus service requests, maintenance coordination, and network quality work in a realistic university setting. Lovely Professional University is the project context; this software does not claim official affiliation with or operation by LPU.

**Current phase: Configurable routing and SLA engine.** This release includes session authentication, role-based API access, campus reference data, issue intake, configurable team routing, persistent SLA deadlines, warnings/breaches/escalations through a periodic Celery sweep, internal notifications, and audit records. Work orders, duplicate detection, feedback, network measurements, and analytics are not implemented yet.

## Stack and structure

- Backend: Python 3.12+, Django 5, Django REST Framework, PostgreSQL, `django-filter`, Pillow, `qrcode`
- Frontend: React 18, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query
- Background services: Celery, Celery Beat, Redis (infrastructure only in this phase)
- Development stack: Docker Compose

    backend/config/       Django settings, URLs, ASGI/WSGI, Celery
    backend/apps/users/   Custom email identity, roles, session auth
    backend/apps/campus/  Campuses, buildings, locations, departments, teams
    backend/apps/issues/  Categories, issues, attachments, status events, filters
    backend/apps/assets/  Asset registry and protected QR endpoint
    frontend/src/         Application shell and role-aware issue workflows
    docs/                 Architecture and domain model

## Local setup

Requirements: Python 3.12+, Node.js 20+, npm, PostgreSQL 16, and Redis. From the repository root:

1. Copy `.env.example` to `.env`. Set a private `DJANGO_SECRET_KEY` and database password. Never commit `.env`.
2. Install and start the backend:

       cd backend
       python -m venv .venv
       .venv\Scripts\Activate.ps1
       pip install -r requirements.txt
       python manage.py migrate
       python manage.py seed_development
       python manage.py runserver

   The seed command prompts for one development password shared by its synthetic test accounts. It creates `system-admin@example.test` as the development Django Admin account. Seed records are synthetic and are not official campus infrastructure or real people.

3. In another terminal, start the frontend:

       cd frontend
       npm install
       npm run dev

The frontend runs at `http://localhost:5173`, the API at `http://localhost:8000/api/`, and Django Admin at `http://localhost:8000/admin/`.

Read [docs/routing-and-sla.md](docs/routing-and-sla.md) for routing precedence, policy selection, the periodic SLA worker, escalation behavior, and endpoints. Configure rules and policies in the administrator UI at `/admin/routing-rules` and `/admin/sla-policies`. The Docker Compose stack includes the Celery worker and Beat service; Beat runs the SLA sweep every minute and does not enqueue one timer per issue.

### Authentication

The React app uses Django’s database-backed session authentication. It requests `/api/auth/csrf/` before unsafe requests, sends the CSRF token in `X-CSRFToken`, and includes browser credentials. The API is configured for the frontend origin in `.env.example`; add any local or deployed frontend origin to both `DJANGO_CORS_ALLOWED_ORIGINS` and `DJANGO_CSRF_TRUSTED_ORIGINS` as appropriate. Production should use HTTPS so secure session and CSRF cookies are enabled (`DJANGO_DEBUG=false`).

### Development seed data

`python manage.py seed_development` is idempotent and creates one explicitly synthetic campus, example buildings and locations, departments, teams, categories, role-specific users, and a small asset inventory. It creates no sample issues. Choose a private password when prompted; all seeded accounts share it for local convenience.

### Tests and checks

The test settings use an isolated in-memory SQLite database, so automated tests do not need a running PostgreSQL server:

       cd backend
       python manage.py check --settings=config.test_settings
       python manage.py test --settings=config.test_settings
       python manage.py makemigrations --check --dry-run --settings=config.test_settings
       cd ..\frontend
       npm run lint
       npm run build

PostgreSQL remains the configured application database. Before development or deployment against PostgreSQL, run `python manage.py migrate` with the project `.env` loaded.

## Docker Compose

Create `.env` from `.env.example`, update its secret and password, then run from the repository root:

       docker compose up --build

Compose waits for PostgreSQL and Redis health, runs migrations once in a dedicated `migrate` job, then starts Django. Celery Worker and Beat wait until Django passes its API healthcheck as well as Redis health, so neither can process tasks against an unmigrated schema. The Compose environment explicitly uses `POSTGRES_HOST=postgres` and `REDIS_URL=redis://redis:6379/0`; no restart loop is used to mask migration failures. Seed records are not created automatically; run `docker compose exec backend python manage.py seed_development` to create them. Open the UI at `http://localhost:5173`. The liveness endpoint is `http://localhost:8000/api/health/`.

## API overview

All resource endpoints require an authenticated session unless noted.

| Method and path | Purpose |
| --- | --- |
| `GET /api/auth/csrf/` | Set the CSRF cookie before login or other writes |
| `POST /api/auth/login/` | Start a session using email and password |
| `POST /api/auth/logout/` | End the current session |
| `GET /api/auth/me/` | Return the signed-in account and team IDs |
| `GET /api/campuses/`, `/api/buildings/`, `/api/locations/` | Read active campus reference data |
| `GET /api/departments/`, `/api/teams/` | Read active departments and teams |
| `GET /api/issue-categories/` | Read active issue categories from the database |
| `GET /api/assets/`, `GET /api/assets/:id/` | Read active assets |
| `GET /api/assets/:id/qr/` | Return a PNG QR code containing the asset QR identifier |
| `GET /api/issues/`, `POST /api/issues/` | List visible reports or create an issue (multipart form supports an optional image) |
| `GET /api/issues/:id/` | Read an authorized issue, its attachments, and recorded status events |
| `POST /api/issues/:id/status/` | Move an issue through an allowed status transition |
| `GET /api/issue-attachments/:id/file/` | Stream an image after issue-level authorization |

Issue collections support page-number pagination (20 per page) and filters: `status`, `priority`, `category`, `location`, `reporter`, `created_after`, and `created_before`. Location and asset selectors support bounded server-side search. Campus, category, and asset writes are restricted to campus or system administrators. See [docs/architecture.md](docs/architecture.md) and [docs/domain-model.md](docs/domain-model.md) for model ownership and visibility rules.

## Current boundaries

Students and staff can create reports and see only their own. Technicians see records assigned to them; supervisors see records assigned to their teams; designated managers and administrators have broader issue visibility. Assignment and routing workflows are not provided yet, so operational assignments are currently a data/permission foundation managed through development administration. Issue photos accept JPEG, PNG, or WebP up to 5 MB and are served only through an authenticated, issue-authorized endpoint.
