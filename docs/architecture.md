# Architecture

## Current phase

The repository has a React single-page application, a Django REST API, and PostgreSQL as the configured application database. Implemented workflows include identity, reference data, issue intake, configurable routing, persisted SLA deadlines, a bounded Celery Beat sweep, internal notifications, audit history, technical staff work orders with evidence and Admin verification, network/device inventory, append-only raw measurements, versioned deterministic per-measurement quality evaluation, Phase 5.3A derived analytics APIs, the Phase 5.3B Network Quality dashboard, Phase 5.3C descriptive historical measurement trends, and Phase 5.4 operator-assisted measurement-to-issue context. Network readings remain supporting evidence; issues remain the operational source of truth. Forecasting, anomaly detection, alerts, and infrastructure polling remain out of scope.

## Frontend

`frontend/src/App.tsx` owns authenticated routing, role-aware navigation, sign-out, and the application shell. `features/auth` handles sign-in; `features/issues` contains issue list, intake, detail, dashboard summary, assignment and status update screens; `features/workorders` contains technical staff queues and Admin review/assignment actions; `features/notifications` provides the recipient-scoped notification inbox and read state; `features/admin` contains routing-rule and SLA-policy forms; `features/assets` reads the asset register; `features/network` contains network inventory, evaluations, operational analytics, and historical trends. UI primitives are in `components/ui.tsx`, shared API calls and CSRF handling are in `lib/api.ts`, and API response contracts are in `types/api.ts`.

TanStack Query owns API data fetching and cache invalidation. React Router provides `/login`, `/dashboard`, `/issues`, `/issues/new`, `/issues/:id`, `/work-orders`, `/work-orders/:id`, `/notifications`, `/profile`, `/assets`, `/network/devices`, `/network/devices/:id`, `/network/networks`, `/network/measurements`, `/network/measurements/:id`, and administrator workflow configuration. Issue, work-order, and network-record lists use database-backed filters and page-number pagination. Network pages are role-gated and provide retry, loading, empty, and submission-feedback states. Operational dashboards show role-scoped queues from persisted work orders; notifications link to relevant issues and support marking items read.

## Identity and permissions

`users.User` is the custom email-based user model and is configured before the first database migration. Email is normalized to lowercase. Passwords use Django’s password hashing and validators. Browser authentication uses Django sessions with `HttpOnly`, `SameSite=Lax` cookies and CSRF tokens on unsafe requests. Session and CSRF cookies are marked secure when `DJANGO_DEBUG=false`; production must use HTTPS.

Roles are `STUDENT`, `STAFF`, `TECHNICAL_STAFF`, and `ADMIN`. Student and employee login accepts an institutional ID or email; Django authenticates the resolved account and returns the database role. Technical specialization is separate from role. Existing administrator identities remain separate accounts even though their former operational roles are consolidated. Frontend navigation reflects these roles, but all access restrictions are enforced in API permission classes and querysets:

- Students and staff can submit and view their own issues. Only staff may request priority handling at submission; the reason, requester, and time are stored. Queue priority is separate from the captured routing/SLA priority.
- Technical staff can view only issues assigned to their active account and update permitted nonterminal status transitions. They cannot resolve, close, or reopen issues directly; work-order verification remains the resolution path.
- Admin can view and manage all issues, configuration, assignments, and work orders across teams.
- Network operations are available to Admin and technical staff whose specialization is Network or IT Support; inventory changes are Admin-only. Raw measurements remain append-only.
- Django Admin access is granted to active Admin-role accounts. No shared administrator account is introduced.

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
| `workorders` | WorkOrder lifecycle, technician assignment, notes, materials, evidence, history, audit and notifications |
| `feedback` | Future satisfaction and reopening feedback boundary |
| `network` | Campus-scoped network inventory, location-linked devices, append-only raw measurements, per-measurement evaluation, and `IssueNetworkContext` provenance links |
| `analytics` | Future database-backed operational summaries |
| `notifications` | Internal per-recipient notification inbox and read state |
| `audit` | Append-only administrative and operational audit records |

Domain models live in the app that owns their lifecycle. Cross-domain references use foreign keys, migrations, and explicit `on_delete` behavior. PostgreSQL indexes cover issue status, priority, category, reporter, and operational assignment lookups. Django REST Framework uses `django-filter` and page-number pagination.

## Campus and issue data direction

The campus structure is `Campus → Building → Location`; a Location may have a parent Location for smaller subareas and may omit a Building for outdoor areas. Departments own optional Teams; a user may belong to multiple teams. Assets reference a Location. Issues reference a reporter, category, Location, optional Asset, optional assigned user/team, controlled priority, and controlled status. IssueEvent stores real creation and status-change events; the UI does not synthesize activity history.

Issue and work-order evidence attachments are restricted to JPEG, PNG, and WebP images, at most 5 MB and 20 megapixels. Files are stored under `MEDIA_ROOT`, but no public media URL is configured. The API streams files through authenticated views that check visibility of the parent issue/work order and sends `nosniff` and private cache headers. Asset QR responses contain the asset’s opaque UUID identifier, not a database password or other secret.

## API conventions

The API root is `/api/`. Serializers validate input and control role-sensitive output; protected views use session authentication and explicit permission classes. Issue lists are scoped before filters are applied, preventing students from retrieving another reporter’s issues by changing query parameters. Issue status changes go through a service that locks and reloads the issue, validates the current lifecycle and assignment, and writes an IssueEvent in one database transaction. This serializes competing transitions against PostgreSQL row state. Issue updates and deletion are not exposed as general CRUD endpoints.

Authentication endpoints are `/api/auth/login/`, `/api/auth/logout/`, and `/api/auth/me/`; `/api/auth/csrf/` initializes the CSRF cookie. Reference endpoints cover campuses, buildings, locations, departments, teams, issue categories, and assets. Issue endpoints support list, create, detail, assignment, scoped `/status/`, role-scoped `/summary/`, and network context read/attach. Network measurement endpoints support an explicit operator action to create an issue through the existing issue serializer and normal routing/SLA pipeline. `IssueNetworkContext` snapshots evaluator version, quality, and primary factor without copying raw readings, which remain on the source measurement. Network context APIs require network-reader access and the existing issue object permission. Work orders remain optional. Network Quality does not automatically create campus issues from threshold breaches. Work orders expose explicit assignment, accept, start, notes, material, evidence, completion, verification, rework, close, and cancel actions. Admin-only APIs manage routing rules and SLA policies. Notifications are user-scoped and attachments use separate authorized file endpoints.

## Seed data and development

`python manage.py seed_development` creates a small, idempotent, synthetic dataset using `.test` emails, synthetic institutional IDs, four roles, and invented campus records. It prompts for a password only when creating accounts; rerunning it does not reset existing passwords. It never inserts sample issue volume or claims that the fictional records are official LPU infrastructure.

Automated tests use `config.test_settings` with an in-memory SQLite database, avoiding a running PostgreSQL service. PostgreSQL remains the configured real application database and must be used for local integration and deployment verification. Docker Compose defines the services but requires an available Docker engine.

## Routing and SLA workflow

Routing and SLA services are database driven and documented in [routing-and-sla.md](routing-and-sla.md). Issue submission calls the services within the database transaction; deadlines are persisted on `Issue`. A Celery Beat sweep, not individual scheduled tasks, handles warnings, breaches and escalation. Routing and policy matching precedence is documented there.

## Later modules

Duplicate detection, feedback, maps/coverage analytics, alerts, anomaly detection, and prediction remain future scope. Phase 5.3A backend aggregations, the Phase 5.3B dashboard, Phase 5.3C descriptive history, and Phase 5.4 operator-assisted issue context, including time windows, filters, provenance, and permission rules, are documented in [network-foundation.md](network-foundation.md); no real-device polling or external monitoring integrations are present. Analytics derive from persisted records and retain the backend permission boundary.
