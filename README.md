# LPU Campus Issue Management & Network Quality Analytics Platform

An academic project for campus service requests, maintenance coordination, and network quality work in a realistic university setting. Lovely Professional University is the project context; this software does not claim official affiliation with or operation by LPU.

**Current phase: Phase 5.4 — Operator-Assisted Network Finding to Issue Context.** The application includes session authentication, role-based API access, campus reference data, issue intake, configurable routing, persistent SLA deadlines and escalation, internal notifications, audit history, technician work orders with private evidence and supervisor verification, network inventory, validated operator-submitted raw measurements, deterministic per-measurement quality evaluation, derived network analytics and historical trends, and an operator-reviewed path to create or contextualize campus issues. Network readings remain supporting evidence; the campus issue remains the operational source of truth.

## Stack and structure

- Backend: Python 3.12+, Django 5, Django REST Framework, PostgreSQL, `django-filter`, Pillow, `qrcode`
- Frontend: React 18, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query
- Background services: Celery, Celery Beat, Redis
- Development stack: Docker Compose

    backend/config/       Django settings, URLs, ASGI/WSGI, Celery
    backend/apps/users/   Custom email identity, roles, session auth
    backend/apps/campus/  Campuses, buildings, locations, departments, teams
    backend/apps/issues/  Categories, issues, attachments, status events, filters
    backend/apps/workorders/  Operational tasks, technician workflow, evidence, verification
    backend/apps/assets/  Asset registry and protected QR endpoint
    backend/apps/network/ Network, device, and append-only measurement records
    frontend/src/         Application shell and role-aware issue/work-order/network workflows
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

Read [docs/routing-and-sla.md](docs/routing-and-sla.md) for routing precedence, policy selection, the periodic SLA worker, escalation behavior, and endpoints. Read [docs/network-foundation.md](docs/network-foundation.md) for network inventory, measurement constraints, permissions, and endpoints. Configure rules and policies in the administrator UI at `/admin/routing-rules` and `/admin/sla-policies`. The Docker Compose stack includes the Celery worker and Beat service; Beat runs the SLA sweep every minute and does not enqueue one timer per issue.

### Authentication

The React app uses Django’s database-backed session authentication. It requests `/api/auth/csrf/` before unsafe requests, sends the CSRF token in `X-CSRFToken`, and includes browser credentials. The API is configured for the frontend origin in `.env.example`; add any local or deployed frontend origin to both `DJANGO_CORS_ALLOWED_ORIGINS` and `DJANGO_CSRF_TRUSTED_ORIGINS` as appropriate. Production should use HTTPS so secure session and CSRF cookies are enabled (`DJANGO_DEBUG=false`).

### Development seed data

`python manage.py seed_development` is idempotent and creates one explicitly synthetic campus, example buildings and locations, departments, teams, categories, role-specific users, a small asset inventory, three synthetic network types, and representative device types. It creates no sample issues or measurements. Choose a private password when prompted; all seeded accounts share it for local convenience.

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
| `GET /api/work-orders/`, `/api/work-orders/:id/` | List and retrieve work orders visible to the signed-in operational role |
| `POST /api/issues/:id/work-orders/` | Create an operational work order from an authorized issue |
| `POST /api/work-orders/:id/assign/` | Assign or reassign to an active technician in the selected team |
| `POST /api/work-orders/:id/accept/`, `/start/` | Accept assigned work and begin field work |
| `POST /api/work-orders/:id/notes/`, `/materials/`, `/evidence/` | Record field notes, materials, and private image evidence |
| `POST /api/work-orders/:id/complete/` | Submit a required resolution summary for supervisor review |
| `POST /api/work-orders/:id/verify/`, `/rework/`, `/close/`, `/cancel/` | Verify or return work, then close or cancel under operational permissions |
| `GET /api/work-order-evidence/:id/file/` | Stream evidence after work-order authorization |
| `GET /api/work-orders/summary/` | Return database-backed work-order counts scoped to the current user |
| `GET /api/notifications/` | List notifications addressed to the signed-in user |
| `POST /api/notifications/:id/read/` | Mark one of the signed-in user's notifications as read |
| `GET, POST /api/networks/` | List or register campus Wi-Fi, LAN, and WAN records |
| `GET, POST /api/network-devices/`, `GET /api/network-devices/:id/` | List/register devices or retrieve a device record |
| `GET, POST /api/network-measurements/`, `GET /api/network-measurements/:id/` | List or append raw measurement records; updates and deletes are not exposed |
| `GET /api/network-measurements/:id/evaluation/` | Return deterministic, versioned per-measurement quality explanation |
| `POST /api/network-measurements/:id/create-issue/` | Create a reviewed campus issue through the normal issue pipeline and attach this measurement as evidence |
| `GET`, `POST /api/issues/:id/network-context/` | Read or attach measurement context, subject to both network-reader and issue-object permissions |
| `GET /api/network-analytics/summary/` | Return actual measurement counts, quality distribution, latest reading, and evaluated primary factors |
| `GET /api/network-analytics/campuses/`, `/locations/`, `/buildings/`, `/devices/`, `/networks/` | Return paginated summaries for represented entities |
| `GET /api/network-analytics/problem-locations/`, `/problem-devices/` | Return locations/devices with poor or critical measurements in deterministic priority order |
| `GET /api/network-analytics/factors/` | Return primary-factor counts and their share of degraded measurements |
| `GET /api/network-analytics/trends/` | Return historical network-quality aggregates over supported time buckets and filters |

Issue and work-order collections support page-number pagination (20 per page); work orders can be filtered by status, team, technician, and issue. Issue search is visibility-scoped and supports bounded server-side searching. Location and asset selectors support bounded server-side search. Campus, category, and asset writes are restricted to campus or system administrators. Network analytics are derived from stored measurements and versioned evaluations; they do not modify source data or represent live infrastructure. Network Quality does not automatically create campus issues from threshold breaches. Contextual issue creation requires an operator to review and explicitly submit the normal issue form; attaching existing evidence does not change issue status, assignment, SLA, notifications, or work orders. See [docs/architecture.md](docs/architecture.md), [docs/domain-model.md](docs/domain-model.md), [docs/work-orders.md](docs/work-orders.md), and [docs/network-foundation.md](docs/network-foundation.md) for details.

## Current boundaries

Students and staff can create reports and see only their own; they have no work-order controls. Technicians see only work orders assigned to their active account. Supervisors see work orders for their teams, while designated managers and administrators have broader operational visibility. Technician assignment requires an active technician who is a member of the selected active team. Issue and work-order images accept JPEG, PNG, or WebP up to 5 MB and are served only through authenticated, scope-checked endpoints. Supervisor verification may resolve an in-progress issue; closing that issue remains a separate issue lifecycle action. Network inventory is visible to technicians, supervisors, IT managers, and campus/system administrators; inventory changes are limited to IT managers and campus/system administrators. Measurements remain append-only operator-submitted records; quality classifications are deterministic explanations and are not live device telemetry. Network measurements never trigger automatic issue or work-order generation.
