# Phase 2 domain model

This document describes the records currently implemented. All campus and seed examples are synthetic development data; they do not describe official LPU infrastructure.

## Identity and organization

- **User** — unique normalized email, full name, optional phone number, one role, active flag, Django password hash, join date, and Django permission fields. Roles are controlled choices.
- **Campus** — named campus record with a unique code and active state.
- **Building** — belongs to one Campus; code is unique within its Campus.
- **Location** — an issue-reporting point in a Building or outdoors; can optionally parent smaller sublocations. It has a controlled location kind, code, description, and active state.
- **Department** — named organizational reference record.
- **Team** — optional Department relationship, active state, and many-to-many User membership.

The intended hierarchy is `Campus → Building → Location`. Teams do not imply an official organizational structure.

## Issue and asset records

- **IssueCategory** — name, description, optional icon identifier, active state, and timestamps. The frontend reads categories from the API.
- **Asset** — unique asset code and generated UUID QR identifier, name, type, Location, active state, and timestamps.
- **Issue** — unique `ISS-YYYY-NNNNNN` ticket number; title and description; required category, Location, and reporter; optional Asset, assigned user, and assigned Team; controlled priority and status; created/updated and resolution/closure timestamps.
- **IssueAttachment** — one validated image file associated with an Issue and uploader, with server-detected content type and timestamp.
- **IssueEvent** — actual creation or status transition, with prior/current status, optional actor and note, and timestamp. It is the activity-history source; arbitrary activity events are not generated.

Priority values are `LOW`, `MEDIUM`, `HIGH`, and `CRITICAL`. Lifecycle states are `OPEN`, `IN_REVIEW`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`, and `REOPENED`. The transition graph is enforced by a domain service that locks and reloads the issue before validating a transition. Active data-driven routing rules match category, location, and priority when an issue is submitted; the selected team/member and every automatic or manual outcome are retained in `Assignment` history. If no rule matches, the issue remains unassigned. Campus/system administrators can manually assign or reassign any active team; supervisors can assign only within their own teams. Reopening retains the original SLA policy, deadlines, breach timestamps, and escalation history.

## Visibility rules

| Role group | Issue visibility | Status changes |
| --- | --- | --- |
| Student, Staff | Their own reports | None |
| Technician | Issues assigned directly to them | Allowed non-terminal transitions on assigned issues; resolving/closing/reopening is denied and resolution must follow work-order verification |
| Supervisor | Issues assigned to a team they belong to, plus unassigned issues for review | Allowed transitions only on issues assigned to one of their teams; unassigned rows are read-only until assigned |
| Facility Manager, IT Manager, Department Head, Campus Admin, System Admin | All issues | Allowed lifecycle transitions |

Visibility is applied to the queryset before filtering and pagination. Attachment retrieval applies the same issue visibility and does not publish uploaded files through a public media route.

## Work-order domain

- **WorkOrder** — an operational task linked to an Issue (multiple work orders may exist per issue), with a unique `WO-YYYY-NNNNNN` number, assigned Team and optional Technician, task summary/instructions, inherited priority, controlled status, creator/completer/verifier, resolution/cancellation/rework text, and accepted/started/completed/verified/closed timestamps.
- **WorkOrderAssignment** — append-only team/technician assignment history, reason, assigning user, and time.
- **WorkOrderEvent** — lifecycle, note, material, and evidence history with actor and status transition fields.
- **WorkOrderNote** — field or operational note attributed to its author.
- **WorkOrderMaterial** — simple material name, quantity, optional note, recorder, and time; this is not an inventory or procurement system.
- **WorkOrderEvidence** — validated private image evidence. It is streamed only to users with work-order visibility.

Work-order lifecycle is `ASSIGNED → ACCEPTED → IN_PROGRESS → COMPLETED → VERIFIED → CLOSED`; a supervisor may return `COMPLETED → REWORK → IN_PROGRESS`, and authorized operational users may cancel before completion. Every transition is enforced by backend services. Completing field work does not resolve or close an issue. Explicit supervisor verification resolves an issue only when it is already `IN_PROGRESS`; closing the issue remains a separate issue transition. Work-order timestamps provide operational timing, while issue SLA deadlines remain on Issue and are never recomputed by creating a work order.

Technicians see only work orders assigned to their active account. Supervisors see work orders belonging to their active teams and may only manage assignments within their team scope. Managers and administrators retain broader operational access. Technician targets must be active technician-role users who are members of the selected active team. Students and staff have no work-order detail visibility or technician controls.

## Network foundation

- **Network** — a campus-scoped Wi-Fi, LAN, or WAN record with a code unique within its campus and an optional building scope.
- **NetworkDevice** — a location-linked access point, switch, router, or gateway assigned to a Network. It may link one existing Asset and stores inventory identity/state; it does not store credentials or poll the device.
- **NetworkMeasurement** — an append-only record attributed to an authenticated user, Network, and campus Location; it may reference a registered NetworkDevice and stores individually nullable latency (ms), packet loss (%), download/upload (Mbps), signal strength (dBm), a user-reported connection state, and server timestamp. At least one numeric measurement is required, values are bounded, and device/network/location relationships are validated.
- **IssueNetworkContext** — a protected, auditable relation between an Issue and a NetworkMeasurement, with creator/time and an immutable snapshot of evaluator version, overall quality, and primary factor. A measurement may support multiple issues; duplicate links to the same issue are prohibited. Raw readings remain on the measurement.

Network inventory and measurement API visibility is granted to technicians, supervisors, IT managers, and campus/system administrators. Inventory mutation is limited to IT managers and campus/system administrators. Measurement create/list/retrieve is available to those operational roles; update and delete methods are not exposed.

The Network app evaluates each record on demand using the deterministic service in version `1.0`. Evaluation includes per-metric states/reasons, an overall worst-metric classification, and a deterministic primary factor. It is not persisted and does not alter source readings. Missing metrics stay unavailable; no persisted measurement can have all numeric fields absent because the model/API enforce at least one reading.

Phase 5.3A derives current-window campus, building, location, device, network, problem-group, distribution, latest-record, and primary-factor summaries from these measurements. No analytics snapshot model is stored. The analytics query reuses the version 1.0 evaluator rather than recalculating classifications. Analytics use the same network-reader role set; current network roles have no row-level campus membership restriction.

Phase 5.4 lets a network reader intentionally create an issue from a measurement or attach that measurement to an issue they may manage. New issue creation uses the normal issue creation, routing, SLA, notification, and audit flow in one transaction. Attaching context alone does not change issue status or assignment and does not create a work order or notification. The user must explicitly submit reviewed issue details; no threshold automatically generates an issue. `IssueNetworkContext` preserves the evaluator result at link time while the measurement remains the source of raw readings. Network readers can view context only when the existing issue visibility/object permission also allows it; technicians can create contextual issues but cannot attach context to existing issues through the issue write API.

## Phase boundaries

Identity, campus structure, issue intake, configurable routing, issue SLA processing, internal notifications, audit history, work orders, network inventory, raw measurement recording, per-measurement quality evaluation, Phase 5.3A backend aggregation, the Phase 5.3B analytics dashboard, Phase 5.3C trends, and Phase 5.4 operator-assisted issue context are implemented. Automatic issue generation, duplicate matching, feedback workflows, browser-based network tests, coverage zones, and prediction remain outside scope.
