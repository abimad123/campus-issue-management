# AGENTS.md

## Project

**Project Name:** LPU Campus Issue Management & Network Quality Analytics Platform

**Institution:** Lovely Professional University (LPU)

**Academic Context:** EduRev / College Project

This is a production-oriented academic project designed around a realistic university campus environment.

The system combines:

1. Campus issue and grievance management
2. Maintenance ticketing
3. IT and network issue management
4. SLA-based routing and escalation
5. Work-order management
6. Duplicate issue detection
7. Resolution and feedback workflows
8. Network quality measurement
9. Campus network coverage analytics
10. Administrative dashboards and reporting

---

# Core Engineering Principle

Build this as a **real software product**, not as a demo or AI-generated prototype.

Prioritize:

- maintainability
- clear architecture
- security
- accessibility
- performance
- responsive design
- realistic workflows
- meaningful validation
- testability
- clean database design
- production-oriented error handling

Do not implement fake functionality merely to make the UI appear complete.

If a feature is not implemented, represent its state honestly.

---

# Technology Stack

## Backend

- Python
- Django
- Django REST Framework
- PostgreSQL
- Celery
- Celery Beat
- Redis
- django-filter
- PostgreSQL `pg_trgm`
- Python `qrcode`

## Frontend

- React
- TypeScript
- Tailwind CSS
- React Router
- TanStack Query
- Recharts
- Leaflet / React Leaflet

## Infrastructure

- Docker
- Docker Compose
- PostgreSQL
- Redis
- Celery Worker
- Celery Beat

---

# Architecture

Use a clean separation between:

- authentication
- users
- campus structure
- issue management
- routing
- SLA
- work orders
- assets
- feedback
- network quality
- analytics
- notifications
- audit logging

Prefer domain-oriented Django applications rather than putting the entire system into one Django app.

Suggested structure:

```text
backend/
    config/
    apps/
        users/
        campus/
        issues/
        routing/
        sla/
        workorders/
        assets/
        feedback/
        network/
        analytics/
        notifications/
        audit/

frontend/
    src/
        components/
        layouts/
        pages/
        features/
        hooks/
        services/
        lib/
        types/
```

---

# User Roles

The platform must support role-based access control.

Roles:

1. Student (`STUDENT`)
2. Staff (`STAFF`)
3. Technical Staff (`TECHNICAL_STAFF`)
4. Admin (`ADMIN`)

Former supervisor and manager responsibilities are consolidated under Admin. Preserve individual accounts and audit history; store technical specialization separately from role.

Never rely only on frontend hiding for authorization.

Every protected operation must be enforced on the backend.

---

# Core Modules

## M1 — Issue Intake & Categorisation

Users can:

- create an issue
- select category
- select location
- attach photos
- optionally link an asset
- provide title and description
- view submission status
- receive a ticket number

Issue reporting should be extremely fast on mobile.

Target:

**Issue submission in under 45 seconds.**

---

## M2 — Routing & Assignment

Issues should be routed based on configurable:

- category
- location
- severity

Routing rules must be stored as data.

Do not hard-code routing rules throughout the application.

Administrators must be able to modify routing rules without changing application code.

---

## M3 — SLA & Escalation

Support:

- SLA policies
- response deadline
- resolution deadline
- warning threshold
- breach detection
- escalation levels
- administrator notifications
- breach history

Store important SLA timestamps directly on the issue/ticket.

Use Celery Beat / periodic sweeping for SLA processing.

Do NOT create one independent scheduled task per ticket.

SLA processing must survive application restarts.

---

## M4 — Work Orders & Resolution

Technicians should receive assigned work.

They can:

- accept work
- update status
- add notes
- record effort
- record parts/materials
- upload resolution proof
- mark work completed

Resolution should support proof photos where appropriate.

---

## M5 — Duplicate Detection

When a new issue is submitted:

Check for potentially related existing issues using:

- title
- description
- location
- time window

Use PostgreSQL trigram similarity where appropriate.

Do not perform an unbounded database scan.

Present potential duplicates to the user/operator as a merge suggestion.

Do not automatically merge without appropriate validation.

---

## M6 — Feedback & Reopen

After resolution:

- request reporter feedback
- capture satisfaction
- allow reopening within a defined window
- track reopen reasons

---

## M7 — Network Quality

Users can perform a browser-based network test.

Capture appropriate measurements such as:

- latency
- download speed
- upload speed
- timestamp
- campus zone
- related network complaint where applicable

Do not pretend to measure something the browser cannot reliably measure.

---

## M8 — Coverage Analytics

Aggregate network measurements by campus zone.

Provide:

- quality score
- average latency
- average download speed
- average upload speed
- measurement count
- weak-zone ranking

Provide a campus map with zone-based visualization.

Use Leaflet.

---

## M9 — Dashboards & Reporting

Provide dashboards for relevant roles.

Metrics may include:

- total issues
- open issues
- resolved issues
- SLA compliance
- SLA breaches
- median resolution time
- p90 resolution time
- reopen rate
- recurring issues
- asset failures
- technician workload
- team throughput
- network weak zones

Reports should be based on actual database data.

---

# Database Principles

Use relational modelling properly.

Important entities include:

- User
- Team
- Issue
- IssueCategory
- Location
- Asset
- RoutingRule
- Assignment
- SlaPolicy
- SlaEvent
- WorkOrder
- Resolution
- Feedback
- NetworkTest
- CoverageZone
- Notification
- AuditEntry

Use foreign keys and constraints wherever appropriate.

Avoid unnecessary JSON blobs when relational modelling is more appropriate.

Use indexes deliberately.

---

# Security

Implement:

- secure authentication
- password hashing through Django
- CSRF protection where applicable
- permission checks
- object-level authorization where necessary
- validation of uploaded files
- safe file handling
- rate limiting where appropriate
- audit logging for important administrative actions

Never expose:

- passwords
- secret keys
- database credentials
- API keys
- environment secrets

Never commit `.env` files containing secrets.

Provide `.env.example`.

---

# API Principles

Use RESTful API design.

Example endpoints:

```text
GET     /api/issues/
POST    /api/issues/
GET     /api/issues/:id/
POST    /api/issues/:id/assign/
POST    /api/issues/:id/resolve/

GET     /api/work-orders/

POST    /api/network-tests/

GET     /api/analytics/coverage/

GET     /api/admin/routing-rules/
POST    /api/admin/routing-rules/
```

Use appropriate HTTP status codes.

Validate all incoming data.

Return consistent error structures.

---

# Frontend Design System

The frontend must NOT look AI-generated.

Avoid:

- excessive gradients
- excessive glassmorphism
- huge rounded containers everywhere
- unnecessary glowing effects
- excessive animated backgrounds
- random decorative blobs
- generic SaaS landing-page aesthetics
- excessive use of purple
- meaningless dashboard cards

The interface should feel like a real university operational platform.

Design goals:

- professional
- institutional
- modern
- calm
- highly usable
- information-dense where appropriate
- visually consistent
- accessible
- responsive

Use a restrained design system.

Prioritize:

- typography
- spacing
- hierarchy
- tables
- filters
- status indicators
- maps
- charts
- meaningful interactions

Animations should be subtle and purposeful.

---

# LPU Context

The application is intended to represent a realistic deployment at:

**Lovely Professional University**

Use realistic campus-oriented terminology.

Example issue categories:

- Electrical
- Plumbing
- Hostel
- Classroom
- Laboratory
- Wi-Fi
- Network
- IT Support
- Transport
- Library
- Security
- Housekeeping
- Furniture
- Air Conditioning
- Academic Administration
- Other

Do not claim that the application is officially affiliated with or operated by LPU unless explicitly authorized.

Use LPU as the academic/project context.

---

# Responsive Requirements

The system must work properly on:

- desktop
- laptop
- tablet
- mobile

Students should be able to report issues quickly from a phone.

Technicians should have a mobile-friendly field interface.

Do not simply shrink the desktop interface.

Design mobile workflows intentionally.

---

# Accessibility

Follow practical accessibility principles:

- semantic HTML
- keyboard navigation
- visible focus states
- sufficient contrast
- meaningful labels
- accessible forms
- accessible error messages
- do not rely only on color to communicate status

---

# Testing

Write automated tests for important business logic.

At minimum test:

- authentication
- role permissions
- issue creation
- issue validation
- routing
- SLA calculations
- SLA breach detection
- escalation order
- duplicate detection
- work-order lifecycle
- feedback/reopen
- network test aggregation
- analytics calculations

Important acceptance scenarios include:

- issue submission under 45 seconds
- correct routing
- SLA survives restart
- escalation fires correctly
- duplicate grouping works
- network measurements aggregate correctly
- recurring failures are identified

---

# Performance

The application should handle a burst of approximately:

**500 issues within one hour**

without queue degradation.

Avoid N+1 queries.

Use:

- `select_related`
- `prefetch_related`
- appropriate indexes
- pagination
- aggregation queries
- background jobs where appropriate

Do not optimize prematurely, but do not knowingly introduce obvious inefficient database patterns.

---

# Git Rules

Make small, meaningful commits.

Use descriptive commit messages.

Never commit:

- `.env`
- secrets
- database dumps
- generated credentials
- unnecessary build artifacts

Keep the repository clean.

---

# Codex Working Rules

Before implementing a major feature:

1. Inspect the existing codebase.
2. Understand the current architecture.
3. Identify affected modules.
4. Check existing tests.
5. Implement the smallest coherent change.
6. Run relevant tests.
7. Fix regressions.
8. Update documentation where necessary.

Do not rewrite working code unnecessarily.

Do not introduce a new library when existing dependencies already solve the problem.

Do not create duplicate components.

Do not silently change architectural decisions.

If an architectural decision is genuinely ambiguous, explain the tradeoff before making a large irreversible change.

---

# UI Implementation Rules

Before creating new UI:

- inspect existing components
- reuse the design system
- maintain consistent spacing
- maintain consistent typography
- maintain consistent status colors
- maintain consistent buttons/forms/tables

Every important page should have:

- loading state
- empty state
- error state
- success feedback where appropriate

Avoid placeholder text such as:

"Lorem ipsum"

"Coming soon"

"AI generated content"

unless the feature genuinely has not been implemented and the state is clearly intentional.

---

# Data Integrity

Never fake analytics.

Dashboard numbers must come from actual database records.

Seed data may be used for development/demo purposes, but it must be clearly separated from production data.

Use realistic seeded campus data for development.

---

# Documentation

Maintain:

- README.md
- architecture documentation
- setup instructions
- environment variable documentation
- API documentation
- database/domain documentation

The README should allow a new developer to run the project locally.

---

# Definition of Done

A feature is not complete simply because the UI exists.

A feature is complete when:

- frontend works
- backend works
- database persistence works
- authorization works
- validation works
- error states work
- relevant tests exist
- tests pass
- responsive behavior is acceptable
- documentation is updated when necessary

Build this project as if another developer will maintain it after us.
