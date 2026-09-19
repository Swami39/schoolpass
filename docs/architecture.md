# SchoolPass architecture

**Status:** Architecture only. No application code in this phase. Hardened after the initial architecture pass.

**Pilot:** 1–10 schools. **Target:** hundreds to thousands of schools on the same design, without a rewrite of tenancy, ingest, or identity.

This document is the spine. Domain depth lives in sibling files. If a sibling disagrees with this file, **this file plus the dedicated domain file after the hardening pass win**; older wording is obsolete.

| # | Topic | Where |
| --- | --- | --- |
| 1 | System architecture | this file |
| 2 | Component architecture | this file |
| 3 | Repository architecture | this file |
| 4 | Database ERD | [database.md](database.md) |
| 5 | Multi-tenancy | this file + [database.md](database.md) |
| 6 | Authentication | [security.md](security.md) |
| 7 | RBAC | [security.md](security.md) |
| 8 | API | [api.md](api.md) |
| 9 | RFID | [rfid.md](rfid.md) |
| 10 | NFC | [nfc.md](nfc.md) |
| 11 | GPS | [gps.md](gps.md) |
| 12 | Notifications | [notifications.md](notifications.md) |
| 13 | Payments | [payments.md](payments.md) |
| 14 | Offline synchronization | this file + [nfc.md](nfc.md) |
| 15 | Event/message | this file + [infrastructure.md](infrastructure.md) |
| 16 | File storage | this file + [api.md](api.md) |
| 17 | Audit | [security.md](security.md) |
| 18 | Logging/monitoring | [infrastructure.md](infrastructure.md) + [security.md](security.md) |
| 19 | Security | [security.md](security.md) |
| 20 | Disaster recovery | [infrastructure.md](infrastructure.md) |
| 21 | CI/CD | [infrastructure.md](infrastructure.md) |
| 22 | Azure | [infrastructure.md](infrastructure.md) |
| 23 | Environment strategy | this file + [infrastructure.md](infrastructure.md) |
| 24 | Testing | [testing.md](testing.md) |
| 25 | Data retention | this file |
| — | Data classification | [security.md](security.md) |
| — | Business invariants | this file |
| — | Decision index | this file |

---

## 1. System architecture

### Choice

A **modular monolith API** (Python / FastAPI) as the system of record, with **asynchronous workers** consuming Azure Service Bus, **PostgreSQL** as the source of truth, **Redis** for hot cache and rate limits, **Azure Blob** for objects, and **three Flutter clients plus two Next.js apps** talking only to versioned HTTPS APIs.

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                   Azure Front Door + WAF                │
                    └───────────────┬─────────────────────────┬───────────────┘
                                    │                         │
                    ┌───────────────▼──────────┐   ┌──────────▼──────────────┐
                    │  Public API (FastAPI)    │   │ Device ingest API       │
                    │  /api/v1  human clients  │   │  /ingest/v1  mTLS/HMAC  │
                    └───────────────┬──────────┘   └──────────┬──────────────┘
                                    │                         │
                                    ▼                         ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │ Postgres (RLS FORCE) │ Redis (live GPS only)            │
                    │ Outbox → Service Bus → Workers                          │
                    │ Blob (private) │ Key Vault │ App Insights / OTel        │
                    └─────────────────────────────────────────────────────────┘

  Flutter: Parent | Teacher | Attendant     Next.js: School Admin | Super Admin
  UHF readers ──HTTPS──► ingest             FCM ◄── notify worker (after inbox row)
  Razorpay webhooks ──HMAC──► payments worker
```

Human traffic and hardware traffic are **separate hostnames and auth modes**. Readers never use a teacher password. Parents never call ingest.

**Identity rule:** a student is a first-class entity. A physical card is not the student. See [database.md](database.md) card model.

### Why it is needed

SchoolPass is an **event-backed operational system**. Gate reads, NFC scans, GPS pings, and payment webhooks must be durable, idempotent, and auditable. A single API process with an explicit ingest surface and an outbox is the smallest design that can be operated for a 1–10 school pilot without treating RFID as CRUD.

### Alternatives considered

| Alternative | Why rejected for v1 |
| --- | --- |
| Microservices per domain | Ops and distributed transactions exceed pilot staffing. Split later at worker/API boundaries that already exist. |
| Serverless-only (Azure Functions for everything) | Cold starts and connection storms are hostile to UHF bursts and Postgres RLS transaction setup. Functions remain valid for *schedulers*. |
| Backend-for-frontend per app | Five BFFs duplicate auth and tenancy. |
| Direct reader → Service Bus | School readers have uneven networks. HTTPS ingest with device credentials is more operable. Bus sits *behind* the API. |

### Tradeoffs

- Mitigation for monolith sprawl: **bounded contexts as Python packages** (`identity`, `tenancy`, `rfid`, `attendance`, `transport`, `academics`, `fees`, `notify`, `audit`).
- Two API entrypoints add infra. That is cheaper than a compromised parent JWT being valid on gate ingest.

### Scalability / security / cost

Pilot load is spiky at bell times. Scale with API replicas + PgBouncer + partitioned event tables. Children’s location, attendance, and payments share one system; blast radius is RLS, RBAC, ingest isolation, private blobs. Dominant later costs: GPS storage, Postgres IOPS at bell time, map tiles — not compute.

---

## 2. Component architecture

| Component | Responsibility |
| --- | --- |
| `api` | AuthN/Z, CRUD, queries, command validation, writes to Postgres + outbox. Establishes RLS transaction context. |
| `ingest-api` | RFID (and optional hardware GPS). mTLS or device HMAC. Tenant from **registered device**, never from client body. |
| `worker-attendance` | Raw RFID/NFC client events → match card assignment → observation → derived attendance → `notify.send` outbox |
| `worker-notify` | Insert durable **inbox** row, then FCM. Never the reverse. |
| `worker-payments` | Verified webhooks only; adapter to fee/subscription ledgers |
| `worker-gps` | Geofence transitions and trip lifecycle — **not** every GPS sample |
| `scheduler` | Subscriptions, fee generation, retention, reader liveness, payment expiry |
| `web-admin` / `web-platform` | Next.js; call `api` only |
| `mobile-*` | Flutter flavors: parent, teacher, attendant |
| `edge-agent` (optional) | On-prem buffer if a reader only speaks TCP/serial |

Pilot may deploy **two containers** (`api` including ingest by hostname, `worker` with all consumers). Module boundaries must still be hard.

Core business transactions **must not call FCM**. FCM is a worker side-effect after the inbox row exists.

---

## 3. Repository architecture

**Monorepo.** One GitHub repository, one Actions graph, one Terraform stack.

```
schoolpass/
  apps/api  apps/worker  apps/web-admin  apps/web-platform  apps/mobile
  packages/domain
  infra/terraform  infra/docker
  docs/
```

Flutter: **one codebase, three application IDs**. CODEOWNERS on `infra/` and `apps/api`.

---

## 4. Database ERD

See [database.md](database.md). Shared PostgreSQL, `tenant_id` on tenant-owned tables, **RLS FORCE**, no per-school database in the pilot.

Student identity is `students.id`. Cards are `physical_cards` + `card_assignments`. Events store resolved `student_id` **and** `card_assignment_id` so history survives card replacement.

---

## 5. Multi-tenancy architecture

### Choice

**Shared database, shared schema, `tenant_id UUID NOT NULL` on every tenant-owned table, PostgreSQL RLS with FORCE.** Application `WHERE tenant_id = …` is **defense in depth only**. It is **not** sufficient security and is **not** the isolation control we rely on.

**No separate database per school initially.**

Enterprise path (not built now): same schema, different DSN on `tenants.db_binding`. RLS remains on.

### Transaction-scoped tenant context (implementation-ready)

Every DML/SELECT on tenant-owned tables runs inside a transaction that sets PostgreSQL GUCs with **`SET LOCAL`** (transaction-scoped, never session-sticky):

| GUC | Type | Meaning |
| --- | --- | --- |
| `app.tenant_id` | UUID text | Current school tenant, or **unset** |
| `app.user_id` | UUID text | Human actor when applicable; **unset** for hardware/system |
| `app.actor_type` | text | `user` \| `device` \| `worker` \| `platform` \| `system` |

Policies (see [database.md](database.md)) authorize rows with:

```sql
tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
```

Missing, empty, or invalid `app.tenant_id` ⇒ **zero rows** and **failed INSERT/UPDATE/DELETE** (`WITH CHECK`). Fail closed. No silent global read.

**Forbidden:** `SET app.tenant_id` without `LOCAL`. **Forbidden:** taking `app.tenant_id` from `X-Tenant-Id` or a JSON body for authorization.

Client-supplied tenant identifiers are ignored for school users. Tenant comes from **verified credentials** as specified below.

### How each entrypoint sets context

| Entrypoint | `app.tenant_id` | `app.user_id` | `app.actor_type` |
| --- | --- | --- | --- |
| School user API (parent, teacher, attendant, school admin) | JWT claim `tid` after membership check | JWT `sub` | `user` |
| Platform super-admin **without** impersonation | **unset** | JWT `sub` | `platform` |
| Platform super-admin **with** impersonation | Explicitly selected tenant, audited | JWT `sub` | `platform` |
| Hardware ingest | Tenant of the **registered reader/tracker**, looked up by device id after signature/mTLS verify | unset | `device` |
| Worker processing a message | `tenant_id` **on the message**, checked equal to the loaded aggregate’s `tenant_id` | optional `actor_user_id` from message | `worker` |
| Scheduler / retention jobs | One tenant at a time per job slice, or `system` on non-tenant tables | unset | `system` |

Body `tenant_id` on an RFID POST is **not** used. If present and not equal to the reader’s tenant, the event is **rejected** (tenant mismatch).

Workers that process an event whose payload tenant ≠ row tenant: **do not process**, dead-letter, alert. That is a release-blocking test.

### Super-admin without accidentally bypassing RLS

- Runtime DB role `schoolpass_app` has **`NOBYPASSRLS`**. There is no “god query” on `students` for the app role.
- Platform tables (`tenants`, `plans`, `subscriptions`, platform billing) are **not** tenant-RLS tables; they use ordinary grants to `schoolpass_app` plus application RBAC (`platform_*` roles).
- Reading another school’s students requires an **impersonation transaction**: write `audit_logs` (`tenant.impersonate`), then `SET LOCAL app.tenant_id`. Support users get time-boxed impersonation. There is **no** API that returns a union of all tenants’ children.
- Break-glass DB role `schoolpass_breakglass` with `BYPASSRLS` exists only for on-call, in Key Vault, not in application connection strings. Use is an infra audit event.

### Connection pooling — no tenant leak

**Decision: PgBouncer transaction pooling.**

1. Checkout connection.
2. `BEGIN`.
3. `SELECT set_config('app.tenant_id', $tid, true)` (and user_id, actor_type) **in this transaction**. `true` = `is_local`.
4. All queries in the same transaction.
5. `COMMIT` / `ROLLBACK` — `SET LOCAL` **vanishes**.
6. Connection returns to the pool with **no tenant GUC**.

If a framework opens autocommit queries, it is a defect: **every** tenant access must be inside the transaction that set GUCs.

Health checks use a transaction **without** tenant GUCs and must only hit non-tenant objects (`SELECT 1`).

Do **not** use session pooling with leftover `SET` (non-LOCAL). Do **not** use DISCARD ALL as the only safety net (transaction-local GUCs are the actual control).

### Clearing / reset

- End of request: commit/rollback is the reset.
- Tests: new transaction per case; assert that a second transaction with unset GUCs reads zero tenant rows.
- Worker: one message = one transaction = one tenant. Never process two tenants in one transaction.

### Cross-tenant testing

Release-blocking cases are listed in [testing.md](testing.md). Isolation is tested **through the API** and **directly as `schoolpass_app` in SQL** with forged/missing GUCs.

### Why / alternatives / tradeoffs / scale / security / cost

Needed because a missed application `WHERE` is a child-data breach. Alternatives (DB-per-school, schema-per-school) fail ops at 10 schools and still need app discipline. RLS planning cost is accepted. Hundreds of schools: partition hot tables. Thousands: tenant-group sharding with the **same** GUC protocol. Cost: one Flexible Server in pilot.

---

## Non-negotiable business invariants

These are product and security invariants. Implementation and tests must not violate them. Product managers may not “shortcut” them for a demo.

1. A student belongs to **exactly one** school tenant.
2. Parents can only access **explicitly authorized** children (`student_guardians`).
3. Teachers can only access **authorized** school resources (assigned divisions/subjects as modeled).
4. Bus attendants can only manage **assigned** buses/trips.
5. A physical card can have **at most one active** student assignment at a time.
6. Historical card assignments **cannot be silently rewritten** (revoke + new row, not UPDATE of identity facts).
7. Raw RFID events are **immutable**.
8. Derived attendance changes (manual correction, void) are **auditable**.
9. Offline NFC events preserve device **`occurred_at`**. Server **`received_at`** is separate.
10. Server-side validation is **authoritative** for bus/student/card assignments.
11. Parents can only view **authorized** bus locations (buses their children are assigned to for that trip/day).
12. GPS tracking occurs **only during authorized active trips**.
13. Client-side payment success is **never** authoritative.
14. Only **verified** payment provider events (or audited offline-cash by finance) can change payment state.
15. Every mutation is attributable to an **authenticated actor** or **trusted hardware/device** (or `system` jobs).
16. Cross-tenant data access is **forbidden** except audited platform impersonation, which still sets a single `app.tenant_id`.
17. Deleted/anonymized PII **cannot be reconstructed** from normal application data (no name in attendance comments, logs, or notification bodies after anonymization).
18. Sensitive data is **never** included in logs unnecessarily.

---

## 6–8. Auth, RBAC, API

See [security.md](security.md) and [api.md](api.md).

- First-party identity, argon2id / OTP, RS256 access JWT (5–15 min), rotating refresh, MFA for school admin and platform.
- RBAC: memberships + `resource:action`; UI hiding is not security.
- REST `/api/v1`, OpenAPI contract, `Idempotency-Key` on event-creating POSTs.

---

## 9–13. RFID, NFC, GPS, notifications, payments

See dedicated documents. Production paths: real devices, real FCM, real Razorpay **verification**. Tests may use cryptographic fixtures and recorded UIDs at the OS adapter — not product endpoints that skip signatures.

RFID is **never** “POST ⇒ student present.” Layers: raw event → processing/dedup → attendance observation → derived attendance record ([rfid.md](rfid.md)).

---

## 14. Offline synchronization architecture

### Choice

**Immutable client events + server idempotency.** Required for attendant NFC/GPS and teacher attendance when offline.

1. Persist locally **before** UI success: `client_event_id` (UUID), `device_id`, `occurred_at` (device), payload, `sync_status`.
2. Sync: `POST /api/v1/sync/events` batches ordered by `device_seq` then `occurred_at`.
3. Unique `(device_id, client_event_id)`. Replay returns the original processing result (`200`).
4. **`occurred_at` ≠ `received_at`.** Example: scan 08:30, sync 09:10 → occurrence **08:30**, received **09:10**.
5. Clock sanity: flag/reject if `occurred_at` > 15 minutes in the future, or older than 36 hours without school_admin override. Flagged events are stored, not silently dropped.
6. Server re-validates tenant, card assignment **as of `occurred_at`**, bus/trip assignment, attendant authorization. Local roster match is a UX hint only.

Conflict: **append-only**. Debounce may attach a new client event to an existing observation (`duplicate_of`) rather than last-write-win.

Unknown UID: immutable client event with `processing_state=unresolved`. Never a fake success.

Details: [nfc.md](nfc.md).

Device outbox: SQLCipher / encrypted Drift. Lost phone: revoke device; old refresh fails; queued events with revoked device credentials are rejected.

---

## 15. Event / message architecture (Azure Service Bus)

### Choice

**Transactional outbox in PostgreSQL + Azure Service Bus Standard (pilot).**

API/ingest transaction: write business rows + `outbox` row in the **same** commit. Publisher: `SELECT … FOR UPDATE SKIP LOCKED`, send to Service Bus, mark published. Consumers are idempotent.

### Authentication

Workers and API use **Azure AD workload identity** (managed identity) to Service Bus. **No application SAS connection strings** in production app settings when workload identity is feasible. Local/dev may use emulator/SAS, never copied to prod.

### Topics / queues (logical)

| Name | When used | Notes |
| --- | --- | --- |
| `rfid.received` | After immutable raw insert | IDs only: `tenant_id`, `rfid_event_id` |
| `client_event.received` | After client_events insert (optional; may process in-request for small batches) | IDs only |
| `attendance.recorded` | After derived attendance commit | IDs; notify worker does not need the student dossier |
| `notify.send` | Command | `notification_command_id`, template key, recipient user id, resource ids |
| `payments.webhook` | After raw webhook store | `payment_webhook_id` only |
| `trip.geofence` | Enter/exit stop or campus | **Not** every GPS sample |
| `trip.lifecycle` | Trip start/stop | |

**Do not put every high-frequency GPS sample on Service Bus.** Live location is Redis (+ durable downsample in Postgres written on the GPS HTTP path). Service Bus is for **transitions** that need notify/audit.

### Message envelope (all messages)

```
message_id          # Service Bus message-id; also stored as outbox.id
correlation_id      # request_id from originating HTTP
tenant_id
idempotency_key     # stable per fact (e.g. rfid_event_id, command_id)
schema_version      # integer, additive
payload             # identifiers only
```

Maximum payload: **32 KB** target, well under Service Bus Standard limits. If a consumer needs more, it **loads from Postgres**.

Schema evolution: add optional fields; never reuse field meanings. `schema_version` bump for incompatible changes; consumers ignore unknown fields.

### Delivery, retry, DLQ

- Delivery: **at-least-once**.
- Retry: Service Bus exponential backoff (e.g. 3–10 attempts) then **dead-letter**.
- DLQ: alert on depth > 0 for payments and attendance; runbook to replay after fix.
- Consumers: unique `(handler_name, idempotency_key)` processed table **or** rely on DB unique constraints (preferred).
- **Do not log complete message bodies.** Log `message_id`, `correlation_id`, `tenant_id`, `topic`, `schema_version`.

### Ordering

Global ordering is **not** required.

**Sessions:** use Service Bus sessions with session id = `bus_id` **only** for `trip.geofence` and `trip.lifecycle` so enter/exit for one bus is serialized. RFID and GPS samples do **not** use sessions (throughput). Attendance debounce is keyed by `(tenant_id, student_id, gate_id, direction, window)` in Postgres, not by bus order.

### Why / alternatives / cost

Outbox avoids phantom publishes. Kafka/Event Hubs are heavier than needed. Service Bus Standard is the pilot SKU; **Premium** if we require VNet + higher isolation — revisit when ingest+notify latency SLOs fail or compliance requires VNet.

---

## 16. File-storage architecture

### Choice

**Azure Blob Storage, private containers, Postgres `files` metadata.** Bytes never authorized by blob key guessability.

Access path (mandatory):

1. Authenticated actor  
2. RBAC permission  
3. Tenant authorization (`app.tenant_id` + RLS on `files`)  
4. Resource ownership/relationship (e.g. parent ↔ student photo)  
5. File metadata authorization (`files.id`, purpose, status=ready)  
6. Short-lived access  

**Never** mint SAS or stream a blob because the client sent a `blob_key`.

### Channel by classification

| Purpose | Class | Access channel |
| --- | --- | --- |
| School marketing assets (logo on public website) | PUBLIC | Public container **or** CDN; not student data |
| Student photos | SENSITIVE_CHILD_DATA | Short-lived **user-delegation SAS** (1–5 min) after checks |
| Announcement attachments (non-results) | CONFIDENTIAL | Short-lived SAS after checks |
| Fee receipts | FINANCIAL | Short-lived SAS after checks |
| Student import CSV | SENSITIVE_CHILD_DATA | **API-proxied**; no SAS to browsers/mobile |
| Academic results PDFs | SENSITIVE_CHILD_DATA | **API-proxied** (avoid SAS leakage in history/screenshots where possible) |
| System backups | SECURITY_SECRET / mixed | Not app-writable; infra roles only |

Staging prefix for uploads; virus scan; promote to final key. Checksum on complete.

### Why / alternatives / cost

Public photos are a breach. Postgres BYTEA is the wrong hot path. CDN in front of private student media is v1 **no**. Egress is the cost meter.

---

## 17–22. Audit, monitoring, security, DR, CI/CD, Azure

See [security.md](security.md) and [infrastructure.md](infrastructure.md).

Wholesale logging is **prohibited** for: student dossiers, payment payloads, notification payloads, authentication secrets, access tokens, GPS streams (except controlled diagnostic flags with TTL, never default).

---

## 23. Environment strategy

| Environment | Purpose | Data | RFID / payments |
| --- | --- | --- | --- |
| `local` | Developer machines | Synthetic **non-child** fixtures | Optional `hardware-sim` **compose profile only**; not in production images |
| `ci` | GitHub Actions | Ephemeral Postgres | Cryptographic fixtures; no real money; no FCM to real devices |
| `staging` | Shared integration | Synthetic or anonymized | Razorpay **test** mode, FCM **debug** apps, lab reader if available |
| `production` | Paying schools | Real | Live PSP, live FCM, real readers |

Production secrets only in Key Vault. Staging is not a copy of production children unless anonymized.

---

## 24. Testing strategy

See [testing.md](testing.md). RLS, cross-tenant, RFID replay, NFC idempotency, payment signatures, parent/bus/file visibility are **release-blocking**.

---

## 25. Data retention strategy

Retention mixes three kinds of decision. Do **not** treat a number in this table as “the law” unless counsel cites a statute.

| Kind | Meaning |
| --- | --- |
| **Product** | What the school product should show (e.g. 90-day bus polyline). |
| **Security / minimization** | Keep high-risk data (GPS, raw RFID, push bodies) no longer than needed. |
| **Legally required** | Accounting, tax, and contracts **must be confirmed by counsel**. Durations below for payments/audit are **conservative product defaults**, not a legal opinion. |

### Default product + minimization policy (pilot)

| Data | Default | After | Notes |
| --- | --- | --- | --- |
| RFID **raw** events | 90 days hot | Aggregate daily counts; optional cool blob archive | Immutable while retained |
| Attendance observations + records | Product: keep for the life of the academic relationship + 3 years after last enrollment **as a product default** | Bind to `historical_subject_id` if PII stripped | Do not DELETE rows solely because the name was anonymized |
| Bus boarding observations | Same as attendance | | |
| GPS samples | 7 days high-frequency retained; 90 days 1-min downsample | Delete coordinates | Product + minimization; not claimed as a legal maximum or minimum |
| Notification inbox bodies | 90 days | Delete body; keep template key + ids | Minimization |
| FCM delivery logs | 90 days | | |
| Payments, invoices, refunds | 8 years **product default pending counsel** | Stay | FINANCIAL |
| Audit logs | 7 years **product default pending counsel** | Optional WORM blob | |
| Card assignments | Retain indefinitely while attendance that references them exists | Never silently rewrite | Needed to interpret history |
| Student operational PII | Soft-hide on withdrawal | Anonymize after a **product** delay (default 12 months) unless the school’s contract requires longer display | See pseudonymization |
| Backups | [infrastructure.md](infrastructure.md) | Encrypted | Follows source classification |

### Pseudonymization (do not destroy meaning)

Do **not** `DELETE FROM students` if attendance, fees, or audit must remain interpretable.

Each student has:

- `id` (internal PK, UUID)
- `historical_subject_id` (separate UUID, **not** derived from name/admission_no, generated at insert)

On anonymization:

- Clear or replace operational PII: legal name, dob, photo_file_id, free-text notes.
- Set `pii_state = anonymized`.
- Guardian links: detach or anonymize parent contact per contract.
- **Keep** `id` and `historical_subject_id` so `attendance_records.student_id` still joins to a non-identifying stub (“Former student”).
- Do not leave names in `audit_logs.diff`, notification bodies, or GPS labels.
- Application APIs for parents stop resolving the child; school/statutory export uses `historical_subject_id`.

Irreversibility: no mapping table from `historical_subject_id` back to deleted names in the app DB. Backups remain a residual risk until they expire (document in DPA).

Tenant offboarding: export → anonymize/wipe per table class → retain FINANCIAL/audit per defaults and contract.

GPS retention is **unchanged in spirit** from the original architecture (short hot window, downsample, delete). No strong reason to keep 1 Hz forever.

---

## Explicit non-goals for this phase

- Application source, screens, Terraform apply, Dockerfiles, placeholder APIs.
- Per-school databases.
- Simulated production RFID/NFC/GPS/payments.
- Storing Aadhaar, full PAN, or biometrics.
- Acting as an unlicensed payment aggregator (see [payments.md](payments.md) external prerequisite).

---

## Architecture decision index

| Decision | Reason | Current choice | Revisit when |
| --- | --- | --- | --- |
| Modular FastAPI monolith + workers | One identity/attendance model; small team; explicit future split points | Packages in one API deployable; workers consume Service Bus | Ingest QPS or team size forces a separate ingest service (mechanical split) |
| PostgreSQL shared DB + FORCE RLS | Isolation without N× migrations; app WHERE is insufficient | Shared schema, `tenant_id`, transaction GUCs | Enterprise isolation SKU sold (dedicated DSN, same schema) |
| Redis | Live bus position, rate limits, OTP, permission cache | Azure Cache for Redis; **not** source of GPS history | Parent poll CPU > 50%; then specialized live store |
| Azure Service Bus Standard | Outbox consumers, retries, DLQ | Standard; workload identity; IDs in messages | VNet/Private Link required, or Standard throughput/latency SLOs fail → Premium |
| RFID HTTPS ingest | School hardware speaks HTTP/TCP better than MQTT | Canonical JSON; HMAC then mTLS; immutable raw events | A chain standardizes on IoT Hub/MQTT — adapter in front of same tables |
| NFC client events | Buses offline; HF short range | Immutable `client_events`; server authoritative; UID-only **not** unclonable | DESFire/NTAG DNA issuance SKU |
| GPS phone + optional tracker | Pilot without waiting on vehicle installers | Redis live; PG downsample; no SB per sample; track **trips** not people 24/7 | Hardware-only fleets; map cost |
| Azure Blob private + metadata | Student media must not be public | RBAC → tenant → relationship → SAS or API proxy | None for public photos |
| FCM HTTP v1 | Real parent push; Flutter-native | Inbox row first, then FCM; one GCP project per env | Notification Hubs only if installation mgmt becomes the bottleneck |
| Razorpay (adapter) | India UPI + webhook signatures | Provider adapter; **two payment rails**; client success ignored | School mandates another PSP; or merchant model cannot be onboarded (blocker) |
| Flutter 3 flavors | Shared NFC/offline/API | One mobile repo | Store policy or vendor-built attendant app |
| Next.js two apps | No platform routes in school bundles | `web-admin`, `web-platform` | — |
| Azure Container Apps | Less ops than AKS for 1–10 schools | API + worker; min replica 1 on worker during school hours | Sidecars/mesh/scale → AKS |
| Terraform | Repeatable Azure | State per env in Blob | — |
| GitHub Actions + OIDC | No long-lived cloud secrets in GitHub | Path-filtered CI; protected prod | — |
| Map tiles on clients | Parents need a map | **Google Maps SDK** with restricted keys; coordinates from our API | Tile cost or policy → Mapbox/Azure Maps |
| PgBouncer transaction mode | Prevent GUC leak; scale connections | `SET LOCAL` / `set_config(..., true)` in the same transaction | Evidence that transaction mode breaks a required session feature |

### External validation prerequisites (not yet confirmed)

These are **not** “TBD in code.” They are **external** gates before production fees or a specific hardware SKU:

1. **Razorpay (or PSP) multi-school merchant model** — Route / sub-merchant / per-school account, KYC, settlement, who is merchant of record, aggregator licensing. Architecture assumes **school is merchant** until this is validated; if invalid, **do not ship fee collection** by pooling funds in SchoolPass.
2. **Counsel:** DPDP processor terms, retention for invoices/audit, parental consent copy.
3. **Apple/Google:** NFC entitlements, background location for attendant app.
4. **UHF reader vendor** for the first pilot school (canonical ingest still holds).
