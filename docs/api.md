# API architecture

**Status:** Architecture only. No routes implemented in this phase. Hardened.

Clients: Flutter (parent, teacher, attendant), Next.js (school admin, platform). Hardware: UHF readers (and optional GPS trackers) on a **different API surface**. Tenant context: [architecture.md](architecture.md) §5 — **never** `X-Tenant-Id` for school-user authorization.

---

## 8. Decision: versioned REST, OpenAPI as the contract

| | |
| --- | --- |
| **Choice** | HTTPS JSON REST under `/api/v1`. FastAPI generates OpenAPI 3. Flutter and TypeScript clients generated from that spec in CI. |
| **Why needed** | Five clients cannot scrape ad-hoc JSON. RFID ingest still fits POST-with-body better than GraphQL. |
| **Alternatives** | GraphQL (flexible parent app, weak file/upload and ingest auth, extra cache semantics); gRPC (great for readers, painful in browsers and Flutter without extra gateway); tRPC (TypeScript-only). |
| **Tradeoffs** | Over-fetching on some parent home screens. Mitigate with dedicated **read models** (`GET /parent/home`) rather than GraphQL. |
| **Scale** | Stateless API replicas. Heavy lists paginated cursor-style. Parent home cached briefly in Redis per `user_id`. |
| **Security** | One documented surface to threat-model. No “internal” JSON from Next.js server to Postgres. |
| **Cost** | Codegen time, not runtime cost. |

**v2** only when breaking. Additive fields are compatible. Deprecate with headers `Sunset`.

---

## Hosts and surfaces

| Host (example) | Auth | Audience |
| --- | --- | --- |
| `api.schoolpass.example` | User JWT / cookie | Humans |
| `ingest.schoolpass.example` | Device mTLS or HMAC | Readers, optional trackers |
| `hooks.schoolpass.example` | Provider signatures | Razorpay only, IP ranges as extra |

Next.js talks **only** to `api`. No server-side Postgres from the web apps in v1 (keeps RLS in one place). If we later add Next.js Route Handlers, they are BFF proxies with the user’s cookie, still not a second data layer.

---

## Resource layout (v1)

Prefix `/api/v1`. All school routes are tenant-implied from the token, **not** `/tenants/{id}/...` for school users.

**Session:** `POST /auth/otp/start`, `POST /auth/otp/verify`, `POST /auth/password/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/mfa/verify`.

**Parent:** children, attendance, bus last-position + polyline, timetable, published results, announcements, invoices, create payment order, notification preferences.

**Teacher:** assigned divisions, class attendance (incl. NFC payload), timetable, result entry (if permitted), announcements.

**Attendant:** trip, roster, `POST /sync/events`, GPS batch, NFC already inside sync events.

**School admin:** CRUD for the entities listed in the product brief (school through reports). Exports as async jobs `POST /exports` → poll or webhook-to-self.

**Platform:** tenants, plans, subscriptions, entitlements, usage, devices-at-risk, health, audit search.

**Sync:** `POST /sync/events` (batch), `GET /sync/roster` (attendant/teacher caches).

**Ingest:** `POST /ingest/v1/rfid/events`, `POST /ingest/v1/gps/samples` (hardware). See [rfid.md](rfid.md), [gps.md](gps.md).

**Webhooks:** `POST /hooks/v1/razorpay`.

---

## Envelope, errors, pagination

Success: resource JSON, no `{ data: { data } }` nesting unless a collection.

Collections: `{ "items": [...], "next_cursor": "..." }`. Default page size 50, max 200.

Errors:

```json
{
  "error": {
    "code": "card_not_assigned_to_bus",
    "message": "Student is not assigned to this bus.",
    "request_id": "..."
  }
}
```

Stable `code` values for mobile. `message` may be localized later; clients key off `code`. HTTP mapping: 401 unauthenticated, 403 forbidden (including RLS empty vs forbidden: **do not leak existence** — parents get 404 for other students), 409 conflict, 422 validation, 429 rate limit.

---

## Idempotency and concurrency

- Header `Idempotency-Key` required on `POST` that creates payments, scans, RFID (readers send their own key; see rfid doc).
- `client_event_id` in sync payloads unique per device.
- Updates to school config use `If-Match` ETag (version column) to avoid two admins clobbering a timetable.

---

## Time and locale

All API timestamps ISO-8601 UTC. Clients format in `tenants.timezone`. Device `occurred_at` must include offset or be UTC; attendant app stores UTC.

---

## Tenant context on API requests

School-user handlers: open transaction, `set_config` from verified JWT (`tid`, `sub`, `actor_type=user`), then queries. Platform: `actor_type=platform`; `tid` unset until impersonation endpoint (audited) sets it. Ingest and hooks: [rfid.md](rfid.md), [payments.md](payments.md).

## File access

Authorize **`files.id`**, never a client-supplied blob key.

`GET /files/{id}/url` — only for types allowed SAS (photos, announcement attachments, receipts) after actor → RBAC → tenant RLS → relationship → metadata. User-delegation SAS 1–5 minutes.

`GET /files/{id}/content` — **API proxy** for results PDFs and import CSVs (and any `classification=SENSITIVE_CHILD_DATA` marked `proxy_required`).

Uploads: `POST /files/uploads` (purpose + content type) → staging SAS → `POST /files/{id}/complete` + checksum → virus scan → promote.

Parent cannot fetch another child’s photo by guessing UUID or blob key (release-blocking).

---

## Rate limits (Redis)

| Bucket | Starting limit |
| --- | --- |
| Auth / OTP per phone | 5 / 15 min |
| Parent GPS poll | 30 / min / user |
| Attendant sync | 60 / min / device |
| RFID ingest per reader | sized to vendor burst (e.g. 50 / s) with 429 + retry-after |
| Admin exports | 10 / hour |

---

## Compatibility with entitlements

API checks `entitlements` (max buses, RFID module on/off). Disabled features: **403** with `code=entitlement_missing`, not a hidden 404, so admin UI can upsell honestly.

---

## Observability of APIs

Every response: `X-Request-Id`. OpenTelemetry traces from FastAPI. Ingest and webhook routes have **separate SLOs** (see [infrastructure.md](infrastructure.md)).

---

## What will not exist

- Unauthenticated “demo” JSON.
- Client-passed `tenant_id` / `X-Tenant-Id` for authorization.
- Blob access by key only.
- A public Swagger UI on production (staging only, behind auth).
- GraphQL playground.
- Client-driven payment capture.
