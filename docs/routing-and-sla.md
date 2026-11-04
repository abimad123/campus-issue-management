# Routing and SLA workflow

## Routing rules

`RoutingRule` records are evaluated only for new issues and only when active. Conditions are conjunctive: a blank category, location, or priority matches any value. Precedence is by the number of specified conditions (most specific first), then ascending `priority_order`, then ascending primary key. This makes ties repeatable. Routing uses the `routing_priority` captured before any staff queue-priority request, so priority requests cannot change team selection. A match selects eligible active technical staff who belong to the target team. The system chooses the lowest active issue workload, then lowest active work-order workload, then stable user ID. A configured target user may win only an otherwise equal workload tie and only when eligible. The assignment record includes the rule and selection reason, and the issue/status/audit/notification records are updated transactionally. If no matching rule or eligible technician exists, an automatic `Assignment` outcome is written and the issue remains in the Admin-visible unassigned queue.

Admin may manually assign/reassign any active team and must select an active technical staff member belonging to that team. Staff and students cannot assign issues. Every assignment is retained as history; current assignment fields on `Issue` are a convenient projection, not the history source.

## SLA policy selection and persistence

`SlaPolicy` holds response and resolution durations and the warning lead time in seconds. Blank category/priority are wildcards. Policy matching uses the captured `routing_priority`, not a staff-requested queue priority, and follows the same specificity, order, and ID tie-break. The selected policy and computed `response_due_at` / `resolution_due_at` are written to the issue at submission. Changing a policy later does not rewrite deadlines on existing issues. Issues without a matching policy remain valid and have no SLA deadlines.

`SlaEscalationLevel` is a relational ladder scoped to a policy. Levels specify the recipient role and elapsed seconds after the first SLA breach. The first breach timestamp and `next_escalation_at` are persisted on the issue, so an application/worker restart cannot lose escalation progress.

## Periodic processing

Celery Beat schedules `apps.sla.tasks.process_sla_sweep` every 60 seconds. It selects a bounded batch (500) of issues whose warning, breach, or escalation timestamp is due, locks those rows inside a transaction, and creates warning/breach/escalation events idempotently. Conditional unique constraints prevent repeated warning or breach events; issue-level timestamps and the escalation level/next timestamp prevent repeated escalation. There is no per-issue Celery task. Late response and resolution transitions also record deadline breaches immediately, so completion just after a deadline cannot hide a breach between sweeps.

## Notifications and audit

`Notification` is an internal, per-recipient inbox record. Issue assignment notifies the selected technical staff member; when no technician is available, active Admin users are notified. SLA warnings and breaches notify active Admin users; escalation levels target the consolidated Admin role. Notification APIs expose only the signed-in recipient's records. No external email or SMS is sent.

`AuditEntry` stores actor, action, entity identity, timestamp, and non-secret context for configuration changes, assignments, status changes, breaches, and escalations.

## Reopening and the original SLA timeline

Reopening an issue continues its original SLA lifecycle. The original policy and response/resolution deadlines are not restarted or extended. Historical breach timestamps, breach events, escalation level, and escalation schedule remain attached to the issue. The periodic sweep includes reopened issues: it resumes pending resolution deadline checks and escalation processing against the persisted timestamps, while unique SLA event constraints, breach timestamps, and notification idempotency prevent duplicate breach records. A response SLA already satisfied by `response_at` is not reconsidered after reopening; an unresolved response may still breach against its original deadline. A new resolution cycle or separate SLA clock is not created.

Issue transitions reload and lock the issue row inside a transaction before checking current assignment, status, and transition validity. This prevents two concurrent transitions from both succeeding based on stale state.

## APIs

- `GET/POST /api/admin/routing-rules/`, `GET/PATCH/DELETE /api/admin/routing-rules/{id}/`
- `GET/POST /api/admin/sla-policies/`, `GET/PATCH/DELETE /api/admin/sla-policies/{id}/`
- `POST /api/issues/{id}/assign/`
- `GET /api/notifications/`, `POST /api/notifications/{id}/read/`
- `GET /api/issues/summary/`

Configuration endpoints and manual assignment require Admin access. The assignment API also validates the selected active team and technical staff membership on the server.
