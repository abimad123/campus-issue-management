# Architecture

## Phase 1 boundary

The repository separates a React single-page application, a Django REST API, and PostgreSQL-backed services. This phase establishes configuration and route boundaries only. No operational domain models, authentication flow, fake records, or analytics are included. `/api/health/` is a liveness endpoint, not a dependency-readiness check.

## Frontend

`frontend/src/App.tsx` owns the application shell and page routes. Shared visual primitives live in `components/ui.tsx`; API transport starts in `lib/api.ts`. React Router handles page navigation and TanStack Query is configured at the application root for server state. The shell is responsive and provides intentional empty states until APIs return real records. Tailwind is configured for utility styling; the current shell also uses a small CSS layer for layout and responsive behavior.

The requested routes are present: `/dashboard`, `/issues`, `/issues/:id`, `/work-orders`, `/network`, `/network/coverage`, `/assets`, `/analytics`, `/reports`, and `/admin`.

## Backend

`backend/config` contains environment-driven settings, root URLs, ASGI/WSGI entry points, and Celery setup. `apps.core` owns cross-cutting liveness and infrastructure smoke-task endpoints. The following Django apps are registered as domain boundaries; they currently contain no models or workflow logic:

| App | Future ownership |
| --- | --- |
| `users` | User profiles, teams, roles, authentication integration |
| `campus` | Campus zones, buildings, rooms, and locations |
| `issues` | Issue intake, categories, lifecycle, and validation |
| `routing` | Data-configured assignment rules |
| `sla` | Policies, deadlines, breach events, and escalation |
| `workorders` | Technician assignments and work completion |
| `assets` | Asset inventory and asset relationships |
| `feedback` | Satisfaction and reopening records |
| `network` | Test measurements and coverage zones |
| `analytics` | Query-backed operational summaries |
| `notifications` | User-facing notification delivery and records |
| `audit` | Administrative and sensitive-action audit events |

Domain models should be introduced alongside the behavior that uses them, with relational constraints and deliberate indexes. Avoid prematurely modeling speculative workflows.

## Data direction

PostgreSQL is the sole configured database. Environment variables provide connection details and secrets. Expected entities as the system grows include User, Team, Issue, IssueCategory, Location, Asset, RoutingRule, Assignment, SlaPolicy, SlaEvent, WorkOrder, Resolution, Feedback, NetworkTest, CoverageZone, Notification, and AuditEntry. Add migrations with each schema change. Keep development seed data separate from production records.

## API direction

The API is rooted at `/api/` and uses Django REST Framework. `/api/health/` currently returns a small liveness response. Future resource endpoints should use REST conventions, serializers for validation, consistent error responses, pagination for collections, and backend permission checks for every protected operation. The frontend API helper centralizes the base URL and fetch behavior.

## Background work

Celery uses Redis for broker and result backend. Worker and Beat services are defined in Compose. A small `debug_task` confirms task discovery and connectivity. No periodic task is scheduled yet. Future SLA processing should use durable timestamps and periodic bounded sweeps rather than one scheduled job per issue.

## Authentication direction

Authentication is not implemented in Phase 1. When introduced, choose the session/token approach based on the deployment and browser threat model; use Django password hashing and enforce role and object-level permissions in the API. Frontend navigation visibility is not an authorization boundary. Keep secrets outside source control and configure production security separately from development defaults.

## Development services

`compose.yaml` defines PostgreSQL, Redis, Django, React/Vite, Celery Worker, and Celery Beat. PostgreSQL and Redis have health checks, and application services use Compose service names for internal connections. Bind mounts support local editing; named volumes preserve database and node dependency state.
