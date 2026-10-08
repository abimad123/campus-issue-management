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

Priority values are `LOW`, `MEDIUM`, `HIGH`, and `CRITICAL`. Lifecycle states are `OPEN`, `IN_REVIEW`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`, and `REOPENED`. The current transition graph is deliberately small and enforced by a domain service. The optional assignment references support visibility policy only; automatic routing and assignment management are not implemented.

## Visibility rules

| Role group | Issue visibility | Status changes |
| --- | --- | --- |
| Student, Staff | Their own reports | None |
| Technician | Issues assigned to them | Allowed transitions on assigned issues |
| Supervisor | Issues assigned to a team they belong to | Allowed transitions on those team issues |
| Facility Manager, IT Manager, Department Head, Campus Admin, System Admin | All issues | Allowed lifecycle transitions |

Visibility is applied to the queryset before filtering and pagination. Attachment retrieval applies the same issue visibility and does not publish uploaded files through a public media route.

## Phase boundaries

No SLA policies or events, configurable routing rules, automatic duplicate matching, full assignment record, work-order lifecycle, feedback, network tests, coverage zones, or analytics entities are created yet. The app packages for later domains remain boundaries until their workflows are designed.
