# Work orders and technician resolution

Work orders represent field tasks created from a reported Issue. They are separate records so one issue can have multiple inspections or repair tasks without duplicating the issue's category, location, reporter, or SLA data.

## Lifecycle

```text
ASSIGNED → ACCEPTED → IN_PROGRESS → COMPLETED → VERIFIED → CLOSED
                                  ↘ REWORK → IN_PROGRESS
ASSIGNED / ACCEPTED / REWORK → CANCELLED
```

Only the assigned active technical staff member can accept, start, record field notes/materials/evidence, and complete their work order. Completion requires a resolution summary of at least 20 characters. Completion submits the task for review; it does not resolve the issue. Admin can verify or request rework across teams. When Admin verifies a work order whose issue is `IN_PROGRESS`, the existing issue transition service moves the issue to `RESOLVED` and records the existing issue history/SLA resolution event. Issue closure remains a distinct operation. Reassignment is allowed only before field work starts; moving an accepted/rework task back to assigned clears acceptance state.

Technical staff may move their assigned issue to `IN_PROGRESS`, but cannot directly resolve, close, or reopen it through the issue status API. Work-order completion must pass through Admin verification before it resolves the issue. Work orders remain optional: Admin can still resolve issues without a work order where the workflow permits.

The technical staff dashboard surfaces assigned work orders, while the Admin dashboard surfaces tasks awaiting verification. The work-order detail view displays the persisted lifecycle state; these views do not create or advance work automatically.

All transitions and permissions are checked in domain services under database transactions and row locks. Team membership, active team/user state, technical staff role, and visibility are validated by the backend. Admin may operate across teams but must use an eligible technician/team pairing.

## Records and history

The workorders app owns `WorkOrder`, `WorkOrderAssignment`, `WorkOrderEvent`, `WorkOrderNote`, `WorkOrderMaterial`, and `WorkOrderEvidence`. Lifecycle, assignment, note, material, and evidence actions also write through the existing append-only audit service. Assignment and notification histories remain internal. Materials are plain task notes (name, quantity, optional note), not an inventory or procurement ledger.

Work orders inherit the issue priority and reference its existing resolution SLA deadline for display. Creation does not alter the issue's SLA policy or timestamps. Work-order accepted, started, completed, verified, and closed timestamps are persisted and can support later operational timing calculations.

Evidence reuses the issue image validator (JPEG, PNG, WebP; 5 MB and 20 megapixels maximum). Files have no public media route. `GET /api/work-order-evidence/:id/file/` checks the caller's work-order scope and responds with `nosniff` and `private, no-store` headers.

## API

All paths require an authenticated session and CSRF token for writes.

| Method | Path | Capability |
| --- | --- | --- |
| GET | `/api/work-orders/` | List work orders in the caller's scope; filter by status, team, technician, or issue |
| GET | `/api/work-orders/:id/` | Read task, issue SLA deadline, assignment, notes, materials, evidence, and history |
| GET | `/api/work-orders/summary/` | Scoped persisted counts by operational state |
| GET / POST | `/api/issues/:id/work-orders/` | List visible issue work orders or create one for an authorized team |
| GET | `/api/work-order-technicians/?team=:id` | Get active technical staff eligible for a team (Admin only) |
| POST | `/api/work-orders/:id/assign/` | Assign/reassign a technician with a reason |
| POST | `/api/work-orders/:id/accept/`, `/start/` | Technician acceptance and work start |
| POST | `/api/work-orders/:id/notes/`, `/materials/`, `/evidence/` | Append field notes, materials, and private image evidence |
| POST | `/api/work-orders/:id/complete/` | Submit resolution summary for review |
| POST | `/api/work-orders/:id/verify/`, `/rework/` | Admin verification or rework request |
| POST | `/api/work-orders/:id/cancel/`, `/close/` | Cancel eligible unstarted work or close verified work |

## UI and role access

Technical staff and Admin see Work orders in navigation. Students and staff do not. Work orders can be created from an authorized issue detail page; the queue and detail pages support filtering, assignment, technician field actions, private evidence preview, review, rework, and closure. Role gates improve navigation usability but do not replace API authorization.

Tests run with the project test settings:

```powershell
docker compose exec backend python manage.py test apps.workorders --settings=config.test_settings
```
