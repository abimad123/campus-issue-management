# Routing and SLA workflow

## Routing rules

`RoutingRule` records are evaluated only for new issues and only when active. Conditions are conjunctive: a blank category, location, or priority matches any value. Precedence is by the number of specified conditions (most specific first), then ascending `priority_order`, then ascending primary key. This makes ties repeatable. A match assigns the target team (and optional active team member), writes an `Assignment`, records the status event, creates internal team notifications, and writes an audit entry. If there is no match, an automatic `Assignment` outcome with a no-match reason is written; the issue remains unassigned and submission succeeds.

Campus and system administrators may manually assign/reassign any active team with a required reason. Supervisors may assign only to one of their own teams. Facility managers, IT managers, and department heads do not have this manual assignment capability. Every assignment is retained as history; current assignment fields on `Issue` are a convenient projection, not the history source.

## SLA policy selection and persistence

`SlaPolicy` holds response and resolution durations and the warning lead time in seconds. Blank category/priority are wildcards. Policy matching uses the same specificity, order, and ID tie-break. The selected policy and computed `response_due_at` / `resolution_due_at` are written to the issue at submission. Changing a policy later does not rewrite deadlines on existing issues. Issues without a matching policy remain valid and have no SLA deadlines.

`SlaEscalationLevel` is a relational ladder scoped to a policy. Levels specify the recipient role and elapsed seconds after the first SLA breach. The first breach timestamp and `next_escalation_at` are persisted on the issue, so an application/worker restart cannot lose escalation progress.

## Periodic processing

Celery Beat schedules `apps.sla.tasks.process_sla_sweep` every 60 seconds. It selects a bounded batch (500) of issues whose warning, breach, or escalation timestamp is due, locks those rows inside a transaction, and creates warning/breach/escalation events idempotently. Conditional unique constraints prevent repeated warning or breach events; issue-level timestamps and the escalation level/next timestamp prevent repeated escalation. There is no per-issue Celery task. Late response and resolution transitions also record deadline breaches immediately, so completion just after a deadline cannot hide a breach between sweeps.

## Notifications and audit

`Notification` is an internal, per-recipient inbox record. Issue assignment notifies active team members; SLA warnings and breaches notify supervisors for the assigned team; escalation notifies the role configured by the level. Notification APIs expose only the signed-in recipient's records. No external email or SMS is sent.

`AuditEntry` stores actor, action, entity identity, timestamp, and non-secret context for configuration changes, assignments, status changes, breaches, and escalations.

## APIs

- `GET/POST /api/admin/routing-rules/`, `GET/PATCH/DELETE /api/admin/routing-rules/{id}/`
- `GET/POST /api/admin/sla-policies/`, `GET/PATCH/DELETE /api/admin/sla-policies/{id}/`
- `POST /api/issues/{id}/assign/`
- `GET /api/notifications/`, `POST /api/notifications/{id}/read/`
- `GET /api/issues/summary/`

Configuration endpoints require campus or system administrator access. Manual assignment allows those administrators and team supervisors (with team scope enforced on the server).
