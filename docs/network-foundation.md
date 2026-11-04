# Phase 5.1–5.4 — Network foundation, evaluation, analytics, and issue context

This phase provides an operational inventory foundation. Records use the existing `Campus → Building → Location` hierarchy and the existing Django session authentication. Development examples created by `seed_development` are synthetic and do not identify real LPU equipment, network names, addresses, or infrastructure.

## Records

- `Network`: campus, optional building scope, campus-unique code, name, type (`WIFI`, `LAN`, or `WAN`), description, active flag, and timestamps.
- `NetworkDevice`: unique device code, name, type (`ACCESS_POINT`, `SWITCH`, `ROUTER`, `GATEWAY`), Network, required Location, optional one-to-one existing Asset, manufacturer/model/serial inventory fields, state (`DEPLOYED`, `MAINTENANCE`, `RETIRED`), and timestamps.
- `NetworkMeasurement`: Network, Location, optional registered device, authenticated recorder, server timestamp, optional latency in milliseconds, packet loss percentage, download/upload in Mbps, signal strength in dBm, connection state, and short note. At least one numeric reading is required. Ranges are enforced in both serializer validation and PostgreSQL constraints. A measurement cannot point to a device on another Network or a mismatched device location.

Inventory has foreign-key protections against deleting referenced campus/location/asset/network rows. Measurements are append-only through the API; update and delete endpoints are not exposed. The API stores no network passwords, management credentials, or telemetry connection configuration.

## API

All routes require an authenticated session. Standard DRF page-number pagination (20 records) applies. Filter and search query parameters are bounded to declared fields.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET, POST; GET/PATCH/PUT/DELETE detail | `/api/networks/` | Browse or manage campus Wi-Fi/LAN/WAN inventory |
| GET, POST; GET/PATCH/PUT/DELETE detail | `/api/network-devices/` | Browse or manage registered infrastructure devices |
| GET, POST; GET detail | `/api/network-measurements/` | Browse, filter, or append raw measurement observations |

Networks filter by `campus`, `building`, `kind`, and `is_active`; search by name, code, campus, or building. Devices filter by `network`, `kind`, `location`, and `state`; search by code, name, vendor/model, network, or location. Measurements filter by network, device, location, connection state, recorder, and `measured_after`/`measured_before`; ordering is permitted by measurement timestamp and numeric values.

## Access rules

- Read inventory and raw measurements: `ADMIN`, or `TECHNICAL_STAFF` with `Network` or `IT Support` specialization.
- Create/update/delete Network and NetworkDevice inventory: `ADMIN`.
- Append a measurement: any of the network-reading roles above; the server sets `recorded_by` and `measured_at`.
- Update/delete measurements: not available through the API.

Frontend navigation and route guards mirror these roles for usability. API permissions remain authoritative.

## Frontend

- `/network/devices` — device inventory and authorized registration form.
- `/network/devices/:id` — device record and its raw measurements.
- `/network/networks` — campus network inventory and authorized registration form.
- `/network/measurements` — paginated raw records, network filter, and authorized manual measurement submission.

The measurement screen records values provided by an authenticated operator. It does not claim browser-derived test results or live device readings. Loading/error/retry/empty/success states are backed by API responses.

## Phase 5.2 — deterministic quality evaluation

`apps.network.services.evaluate_measurement` evaluates one stored measurement at request time. It is deterministic and versioned as `1.0`; evaluations are not persisted, so original measurements remain append-only and are never rewritten. If evaluator policy changes later, the version identifies the policy used for the current response; this version does not provide historical snapshots.

For latency and packet loss, values at or below the listed boundary receive that quality; higher values step down:

| Quality | Latency (ms) | Packet loss (%) |
| --- | ---: | ---: |
| Excellent | ≤30 | ≤1 |
| Good | ≤60 | ≤3 |
| Fair | ≤100 | ≤5 |
| Poor | ≤200 | ≤10 |
| Critical | >200 | >10 |

For throughput, values at or above the boundary receive the quality; lower values step down:

| Quality | Download (Mbps) | Upload (Mbps) |
| --- | ---: | ---: |
| Excellent | ≥100 | ≥50 |
| Good | ≥50 | ≥25 |
| Fair | ≥20 | ≥10 |
| Poor | ≥5 | ≥2 |
| Critical | <5 | <2 |

Signal quality is Excellent at ≥−50 dBm, Good at ≥−60, Fair at ≥−67, Poor at ≥−75, and Critical below −75. Production records currently store signal as integer dBm, while the service handles decimal inputs deterministically as well.

Overall quality is the worst classification among available numeric metrics. No missing metric is treated as zero; if all numeric metrics are absent, the result is `INSUFFICIENT_DATA`, except `DISCONNECTED`, which always produces Critical. `DEGRADED` caps a numeric result at Fair; a worse measured classification remains worse. `CONNECTED` does not downgrade metric results. `UNKNOWN` does not infer quality. When classifications tie, the primary factor is selected in fixed order: connection status (only when it affects the result), packet loss, latency, signal strength, download, upload. Responses include every metric's availability, quality, reason, primary factor, measurement reference, and `evaluation_version`.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | `/api/network-measurements/:id/evaluation/` | Return a single versioned evaluation, subject to the same read permission as the raw record |

The paginated measurement response also contains a compact/full `quality_evaluation` object to avoid per-row evaluation requests. Frontend detail is available at `/network/measurements/:id`; unavailable readings remain visibly “Not recorded.” The list is filterable by existing database fields (not derived quality). No database migration is required.

## Phase 5.3A — derived network quality analytics

Phase 5.3A provides derived network quality analytics from stored measurements. The service in `apps.network.analytics` reads the current measurement records and calls the Phase 5.2 evaluator once per selected record. Analytics are calculated on request; no snapshots, caches, changes to raw records, or alternate quality rules are introduced. Current results represent the synthetic development dataset and must not be read as live or official LPU network status.

### Windows and filters

- Default: trailing 24 hours ending at the request-time `now`.
- `range=24h`, `range=7d`, or `range=30d` select a predefined trailing window.
- Explicit ISO-8601 `start` and `end` values must both be supplied and include timezone offsets. When both are supplied they take precedence over `range`. The interval is half-open: `start <= measured_at < end`; `start` must be earlier than `end`.
- Every response includes the selected timezone-aware start, end, range label, and evaluation version.
- Supported filters: `campus`, `building`, `location`, `network`, `device`, `device_type`, `network_type`, `quality`, and `connection_state`. IDs must be positive integers and enum values must be valid. `source` is not supported because `NetworkMeasurement` has no source field; the API rejects unsupported query keys rather than implying it filtered data.
- Quality filtering uses the Phase 5.2 evaluator result before counts and groups are calculated.

### Summary rules

The summary reports actual measurement count, six quality buckets (five normal levels plus `INSUFFICIENT_DATA`), poor and critical counts, latest measurement and its evaluated quality, and primary-factor counts. An empty window returns zero counts/percentages, `INSUFFICIENT_DATA` as the overall result, and no latest measurement.

Overall window quality is the worst normal quality represented (`CRITICAL`, then `POOR`, `FAIR`, `GOOD`, `EXCELLENT`); `INSUFFICIENT_DATA` is returned only when there is no normal quality result. It is not a statistical average. Distribution percentages use the selected total as denominator and two decimal places. Largest-remainder allocation distributes rounding residuals in stable quality-level order so a non-empty distribution sums to exactly 100.00%; empty distributions contain zero percentages. Persisted records currently require at least one numeric reading, but the insufficient-data bucket remains supported for evaluator outcomes.

“Degraded measurements” for factor reporting means measurements evaluated as `FAIR`, `POOR`, or `CRITICAL`; `EXCELLENT`, `GOOD`, and `INSUFFICIENT_DATA` are not in that denominator. Each reported primary-factor percentage is `factor count / degraded measurement count × 100`, rounded to two decimal places. Factors come only from the Phase 5.2 evaluator's `primary_factor`; raw values are not reinterpreted.

### Read-only APIs

All analytics routes reuse the network measurement read permission (Admin or technical staff specialized in Network/IT Support). Each request requires session authentication. Summary is unpaginated; grouped lists use the default DRF page-number size of 20 and include the time window in the response. General grouped lists sort by display name/identifier ascending. Problem lists contain only location/device groups with at least one poor or critical record and sort by critical count descending, poor count descending, latest measured time descending, then identifier ascending.

| Method | Endpoint | Result |
| --- | --- | --- |
| GET | `/api/network-analytics/summary/` | Window totals, distribution, overall quality, latest measurement, and primary factors |
| GET | `/api/network-analytics/campuses/` | Campus summaries for represented campuses |
| GET | `/api/network-analytics/locations/` | Location summaries with building context |
| GET | `/api/network-analytics/buildings/` | Building summaries for represented buildings |
| GET | `/api/network-analytics/devices/` | Device summaries with neutral quality terminology |
| GET | `/api/network-analytics/networks/` | Network summaries |
| GET | `/api/network-analytics/problem-locations/` | Locations with poor/critical measurements in the specified order |
| GET | `/api/network-analytics/problem-devices/` | Devices with poor recent measurements in the specified order |
| GET | `/api/network-analytics/factors/` | Paginated primary-factor counts and degraded-measurement percentages |

There is no row-level campus membership/scope on current network-read roles; those roles see the same campus-wide network dataset as existing measurement APIs. The optional `campus` filter selects a campus; it does not grant additional access. No analytics database tables or migrations were added.

## Phase 5.3B — Network Quality dashboard

The `/network-quality` page is available through the existing network-operations navigation to Admin and network/IT-support technical staff. It uses the Phase 5.3A read-only analytics API; frontend role gating is a usability layer only, and backend permissions remain authoritative.

The page presents the backend summary and quality distribution, attention-ranked problem locations and devices, campus/building/location/device/network summaries, primary degradation factors, and recent raw measurements. It supports the 24-hour, 7-day, and 30-day windows, plus the analytics API's campus, building, location, network, device, device type, network type, quality, and connection-state filters. Filter updates request fresh server-side results; Clear filters returns to defaults. All grouped analytics results and raw measurements use their server pagination rather than requesting oversized pages. Each section has loading, empty, error, and retry behavior. Summary/distribution has its own retry; Refresh data invalidates dashboard queries without polling.

Recent measurements use the raw measurement endpoint and the time window returned by the analytics summary. That endpoint currently supports network, location, device, and connection-state filters, but not campus/building, device/network type, or derived quality. The page labels this limitation rather than implying the raw rows honor filters unavailable on that API. The quality chart is a simple horizontal bar visualization accompanied by a semantic table. Tables retain horizontal scrolling on narrow screens; filters and summary blocks stack for mobile. Status labels include text and never rely on color alone.

No dedicated frontend test framework is configured in this repository; frontend verification for this page uses the existing lint, production build, and browser checks. The dashboard does not add analytics calculations, store synthetic values in the client, or claim live network telemetry.

## Explicit exclusions

Phases 5.3A–5.3B provide backend aggregation and its operational dashboard only. They do not implement heatmaps, maps, trend visualization, weak-zone ranking, predictive analytics or maintenance, anomaly detection, AI/ML, automatic alerts or notifications, automatic issue/work-order creation, work-order automation, real-time monitoring, SNMP, real AP/router polling, remediation automation, or external monitoring integrations.

## Phase 5.3C — Historical Network Quality Trends

Historical trends are descriptive summaries of stored network measurements. They are derived on request from `NetworkMeasurement` and the Phase 5.2 evaluator; no trend snapshots, duplicated measurements, or synthetic history are stored. Quality levels and primary evaluated factors come from the evaluator rather than SQL or client-side reclassification.

`GET /api/network-analytics/trends/` is read-only and uses the same authenticated network-measurement readers as the Phase 5.3A analytics endpoints: Admin and Network/IT Support technical staff. Students, Staff, and technical staff with other specializations receive 403; anonymous requests require authentication. The current role model does not provide row-level campus isolation; filters narrow the visible dataset but are not security boundaries.

The endpoint supports `range=24h|7d|30d` (default `24h`) and explicit timezone-aware ISO-8601 `start` and `end`. Explicit values must be provided together and take precedence over `range`. The interval is start-inclusive and end-exclusive, following Phase 5.3A. Durations up to 24 hours use local-time hourly buckets; longer periods, including 7-day and 30-day ranges, use local-time daily buckets. Explicit ranges use the same duration-based rule. Only buckets containing measurements are returned; no zero-filled periods are fabricated. A fully empty window returns `buckets: []` and comparison status `NO_DATA`.

Supported narrowing filters are `campus`, `building`, `location`, `network`, and `device`. Compatible filters combine against the same measurement query. Incompatible hierarchy/entity pairs return a clear 400 validation response. The filters reuse measurement relationships and add no campus access-control behavior.

Each populated bucket contains total measurements; counts and percentages for Excellent, Good, Fair, Poor, Critical, and Insufficient Data; degraded count (Fair + Poor + Critical); Poor + Critical count; latest measurement timestamp; and overall bucket quality, defined as the worst meaningful evaluator quality present (or Insufficient Data when none is meaningful). Percentages use the bucket's measurement total as denominator and are rounded to two decimal places using the existing analytics largest-remainder convention. Evaluator-selected primary factors are summarized by bucket and are not presented as confirmed physical root causes.

The comparison is descriptive only: it compares the first and latest populated buckets' degraded percentages. A lower latest value is `IMPROVED`, a higher value is `WORSENED`, and equal values are `STABLE`; the reported delta is in percentage points. Empty data returns `NO_DATA`; fewer than two populated buckets returns `NO_COMPARISON` with null comparison values. It is not a forecast, anomaly detector, or risk score.

The `/network-quality` page includes a Historical Trends section driven by the existing 24h/7d/30d controls and the selected campus, building, location, network, and device filters. It provides a restrained stacked distribution chart, an accessible values table, primary evaluated factors by bucket, and the backend comparison. Loading, section-local retry, and honest empty states do not block the existing dashboard. The visualization scrolls within its own region on narrow viewports; tabular values remain available independently of the chart.

Trend queries filter the timestamp and selected foreign keys in PostgreSQL, then fetch selected rows in chronological order with related network, device, and location data selected in the same query. The Phase 5.2 evaluator runs once per measurement and results are grouped in memory. The existing measured-time and relationship indexes are used; no new index or migration was needed. No forecasting, anomaly detection, alerts, notifications, issue/work-order automation, polling, or external telemetry is implemented.

## Phase 5.4 — operator-assisted network finding to issue context

Network findings may support campus operations, but the Issue remains the operational source of truth. **Network Quality does not automatically create campus issues from threshold breaches.** An authorized network operator must review the raw measurement and current evaluation, edit the issue fields, and explicitly submit the form before an issue is created. Measurements remain operator-submitted data, not live telemetry.

### Context relationship and provenance

`IssueNetworkContext` joins an Issue to a `NetworkMeasurement`. It stores `created_by`, `created_at`, and a snapshot of `evaluator_version`, `overall_quality`, and `primary_factor` as evaluated when the link is created. Raw readings, network/device/location relationships, and measurement time remain on the immutable measurement. A measurement may support more than one issue, while a unique `(issue, network_measurement)` constraint prevents a duplicate attachment to the same issue. The issue, measurement, and creator are deletion-protected while context exists.

### APIs and workflow

| Method | Endpoint | Behavior |
| --- | --- | --- |
| POST | `/api/network-measurements/:id/create-issue/` | Validate editable issue details with the normal issue serializer, create the Issue, run existing routing/SLA/notification behavior, then attach this evidence snapshot in the same database transaction |
| GET | `/api/issues/:id/network-context/` | Return paginated source measurements and their stored evaluator snapshots, after issue-object and network-reader authorization |
| POST | `/api/issues/:id/network-context/` | Attach one existing measurement to a manageable issue; duplicate pairs return a validation error and no unrelated workflow events are generated |
| GET | `/api/issues/?search=...` | Search tickets, title, description, and location only within the caller's existing issue visibility scope; results remain paginated |

The measurement evaluation page offers **Create Issue** to network readers and **Attach to Existing Issue** only to Admin. Create Issue opens the standard issue form with editable title/description, prefilled measurement location, and an existing Wi-Fi/Network category when available; if no matching category exists the operator must choose one. The form displays the measurement timestamp, network/device, location, quality, primary factor, evaluator version, and available readings as supporting evidence. Opening it performs no write. Normal issue creation runs its existing routing, SLA, notification, and audit behavior; work orders remain optional and are never created automatically.

On issue detail, the Network Context section is requested only for network-reader roles. It shows the provenance snapshot and source reading summary and links to the original measurement evaluation. The API requires both network-reader permission and the existing issue object permission: student/staff do not have network access; technical staff may create a new contextual issue using existing issue-creation permission and view context only for assigned issues, but cannot attach context to existing issues. Admin can attach context to any issue. Frontend role checks are for usability and do not replace API enforcement.

Create-issue and attach operations are transactional. `IssueNetworkContext` is protected against measurement, issue, and creator deletion, and records an audit event when attached to an existing issue. Context attachment alone sends no notification and does not alter assignment, status, SLA, or work orders. No fuzzy matching, duplicate issue search, automated ticket generation, threshold alerting, or issue/work-order automation is included in Phase 5.4.
