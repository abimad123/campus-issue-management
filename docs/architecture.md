# Architecture

## Current phase

The repository has a React single-page application, a Django REST API, and PostgreSQL as the configured application database. The current phase implements identity, reference data, issue intake, configurable routing, persisted SLA deadlines, a bounded Celery Beat sweep, internal notifications, and audit history. Work orders, duplicate detection, feedback, network measurements, and analytics remain later work; inactive screens are labelled honestly.

## Frontend

`frontend/src/App.tsx` owns authenticated routing, role-aware navigation, sign-out, and the application shell. `features/auth` handles sign-in; `features/issues` contains issue list, intake, detail, dashboard summary, assignment and status update screens; `features/admin` contains the routing-rule and SLA-policy forms; `features/assets` reads the asset register. UI primitives are in `components/ui.tsx`, shared API calls and CSRF handling are in `lib/api.ts`, and API response contracts are in `types/api.ts`.

TanStack Query owns API data fetching and cache invalidation. React Router provides `/login`, `/dashboard`, `/issues`, `/issues/new`, `/issues/:id`, `/profile`, `/assets`, `/admin/routing-rules`, `/admin/sla-policies`, and explicitly inactive future module routes. The issue list uses database-backed filters and page-number pagination. The issue form loads category, location, and asset options from APIs and accepts one optional image.

## Identity and permissions

`users.User` is the custom email-based user model and is configured before the first database migration. Email is normalized to lowercase. Passwords use Django’s password hashing and validators. Browser authentication uses Django sessions with `HttpOnly`, `SameSite=Lax` cookies and CSRF tokens on unsafe requests. Session and CSRF cookies are marked secure when `DJANGO_DEBUG=false`; production must use HTTPS.

Roles are `STUDENT`, `STAFF`, `TECHNICIAN`, `SUPERVISOR`, `FACILITY_MANAGER`, `IT_MANAGER`, `DEPARTMENT_HEAD`, `CAMPUS_ADMIN`, and `SYSTEM_ADMIN`. Frontend navigation reflects these roles, but all access restrictions are enforced in API permission classes and querysets:

- Students and staff can submit and view their own issues.
- Technicians can view issues assigned to them and update permitted status transitions.
- Supervisors can view and update issues assigned to one of their teams.
- Facility and IT managers, department heads, campus administrators, and system administrators have broader issue visibility.
- Campus and system administrators can modify campus reference data, issue categories, and assets.
- Django Admin access requires a staff account; seeded system administrator is a superuser for local development.

No public registration endpoint exists. Create initial operators through `createsuperuser` or the explicitly synthetic development seed command.

## Backend app ownership

| Django app | Current ownership |
| --- | --- |
| `users` | Custom identity model, role definitions, email/password login, session lifecycle, API role checks |
| `campus` | Campus, Building, Location, Department, Team and team membership |
| `issues` | IssueCategory, Issue, image attachments, actual status events, list filters and visibility |
| `assets` | Asset inventory, UUID QR identity, QR image response |
| `core` | Health/liveness endpoint and infrastructure smoke task |
| `routing` | Data-driven routing rules, assignment history, deterministic matching and controlled reassignment |
| `sla` | SLA policies, escalation ladder, SLA events, policy selection and bounded periodic processing |
| `workorders` | Future work assignment and completion boundary |
| `feedback` | Future satisfaction and reopening feedback boundary |
| `network` | Future measurements and coverage boundary |
| `analytics` | Future database-backed operational summaries |
| `notifications` | Internal per-recipient notification inbox and read state |
| `audit` | Append-only administrative and operational audit records |

Domain models live in the app that owns their lifecycle. Cross-domain references use foreign keys, migrations, and explicit `on_delete` behavior. PostgreSQL indexes cover issue status, priority, category, reporter, and operational assignment lookups. Django REST Framework uses `django-filter` and page-number pagination.

## Campus and issue data direction

The campus structure is `Campus → Building → Location`; a Location may have a parent Location for smaller subareas and may omit a Building for outdoor areas. Departments own optional Teams; a user may belong to multiple teams. Assets reference a Location. Issues reference a reporter, category, Location, optional Asset, optional assigned user/team, controlled priority, and controlled status. IssueEvent stores real creation and status-change events; the UI does not synthesize activity history.

Issue attachments are restricted to JPEG, PNG, and WebP images, at most 5 MB and 20 megapixels. Files are stored under `MEDIA_ROOT`, but no public media URL is configured. The API streams files through an authenticated view that checks visibility of the parent issue and sends `nosniff` and private cache headers. Asset QR responses contain the asset’s opaque UUID identifier, not a database password or other secret.

## API conventions

The API root is `/api/`. Serializers validate input and control role-sensitive output; protected views use session authentication and explicit permission classes. Issue lists are scoped before filters are applied, preventing students from retrieving another reporter’s issues by changing query parameters. Issue status changes go through a service that validates the lifecycle and writes an IssueEvent in one database transaction. Issue updates and deletion are not exposed as general CRUD endpoints.

Authentication endpoints are `/api/auth/login/`, `/api/auth/logout/`, and `/api/auth/me/`; `/api/auth/csrf/` initializes the CSRF cookie. Reference endpoints cover campuses, buildings, locations, departments, teams, issue categories, and assets. Issue endpoints support list, create, detail, assignment, scoped `/status/`, and role-scoped `/summary/`. Admin-only APIs manage routing rules and SLA policies. Notifications are user-scoped and attachments use a separate authorized file endpoint.

## Seed data and development

`python manage.py seed_development` creates a small, idempotent, synthetic dataset using `.test` emails and invented campus records. It asks for a local password shared by those accounts. It never inserts sample issue volume or claims that the fictional records are official LPU infrastructure.

Automated tests use `config.test_settings` with an in-memory SQLite database, avoiding a running PostgreSQL service. PostgreSQL remains the configured real application database and must be used for local integration and deployment verification. Docker Compose defines the services but requires an available Docker engine.

## Routing and SLA workflow

Routing and SLA services are database driven and documented in [routing-and-sla.md](routing-and-sla.md). Issue submission calls the services within the database transaction; deadlines are persisted on `Issue`. A Celery Beat sweep, not individual scheduled tasks, handles warnings, breaches and escalation. Routing and policy matching precedence is documented there.

## Later modules

Work orders, duplicate detection, feedback, network measurement, maps, analytics, and prediction remain future scope. When implemented, derive analytics from persisted records and retain the current backend permission boundary.
