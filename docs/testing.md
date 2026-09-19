# Testing strategy

**Status:** Architecture only.

Once implementation starts, the suites below **block merge and release**. Architecture supports **deterministic** integration tests without production devices or real money.

---

## 24. Decision: test isolation, money, and hardware crypto where being wrong harms a child

| Layer | What | Tooling |
| --- | --- | --- |
| Unit | Debounce, assignment as-of, fee remaining, OTP hash | pytest |
| Domain | Observation vs record, card replacement history | pytest |
| API contract | OpenAPI, authz matrix | pytest + httpx |
| **RLS** | `schoolpass_app` missing GUC → 0 rows; wrong tenant → 0 rows; FORCE on | pytest + real Postgres |
| Ingest | HMAC fixtures, replay, skew, unknown/disabled reader | pytest |
| Webhook | Razorpay **documented test signatures** | pytest |
| Web | Admin critical paths | Playwright |
| Mobile | NFC **OS adapter** recorded UID; outbox real | Flutter test |
| Load | Bell-time ingest | k6 staging |
| Restore | Backup to scratch | infra change |

### Why / alternatives / cost

Mocks-only Postgres will not catch RLS. E2E-only will not hit mTLS easily. CI uses synthetic people. GitHub minutes ≪ a cross-tenant incident.

---

## Release-blocking tests (must exist)

### PostgreSQL RLS and tenant context

- Tenant A cannot **read** Tenant B students, attendance, GPS, payments, files, cards.
- Tenant A cannot **modify** Tenant B rows (UPDATE/DELETE/INSERT with B’s `tenant_id` fails CHECK).
- Missing `app.tenant_id`: zero rows, failed writes.
- Invalid GUC: fail closed.
- After COMMIT, pooled connection used with **unset** GUC cannot see A’s data (leak test).

### Cross-tenant negative (API)

- Tenant A reading Tenant B data → 404/403 as specified.
- Tenant A modifying Tenant B data.
- Tenant A accessing Tenant B **files** (SAS mint and proxy).
- Tenant A accessing Tenant B **payments/invoices**.
- Tenant A accessing Tenant B **GPS/trips**.
- Parent of child in A cannot see B.

### Workers

- Message `tenant_id` ≠ row tenant → **no processing**, DLQ/error, no attendance, no notify.
- Worker with **missing** tenant GUC cannot read tenant tables.

### RFID

- Unknown reader, disabled reader, invalid signature, malformed body, replayed nonce, duplicate `device_event_id`, signature clock skew, tenant mismatch in body → rejected; **no** derived present.
- Accepted raw event does not create attendance until processing.
- Admin can trace record → observation → raw event.

### NFC offline / idempotency

- `occurred_at` 08:30 / `received_at` 09:10 preserved.
- Replay `client_event_id` → one observation.
- Wrong bus / unauthorized attendant / no trip → rejected_* retained, no parent board.
- As-of assignment after card replacement.

### Payments

- Invalid webhook signature → no ledger change.
- Duplicate `provider_event_id` → one capture.
- Client “success” without webhook → invoice not `paid`.

### Authorization / visibility

- Role × endpoint matrix (parent, teacher, attendant, school_admin, platform).
- Parent-child: only `student_guardians`.
- Bus: parent only assigned buses; attendant only assigned trip; teacher no GPS v1.
- File access: relationship + tenant + RBAC; blob_key alone insufficient.

---

## Deterministic fixtures (allowed vs forbidden)

| Allowed in tests | Forbidden as a product stand-in |
| --- | --- |
| HMAC keys and Razorpay **test** signature vectors | Production skip-verify if `APP_ENV=dev` leaked |
| NFC adapter with a recorded UID | Admin “simulate gate” writing attendance without ingest |
| GPS NMEA / JSON fixes | Random walk presented as live production bus |
| Fake device_id in CI device directory | Unsigned ingest in production images |

`hardware-sim` compose profile: local only ([architecture.md](architecture.md) §23).

---

## Authz matrix examples

Parent `GET /students/{other}` → 404; attendant `POST` results → 403; teacher bus_board for unassigned bus → 422 `card_not_assigned_to_bus`; platform without impersonation `GET /students` → empty/403.

---

## Coverage policy

No vanity 100% line target. **Required coverage:** ingest auth, webhook verify, RLS policies, guardian isolation, file authorize, worker tenant mismatch.

---

## Release evidence

Staging: health, seeded teacher login, cross-tenant forbidden. Production smoke: health + synthetic canary tenant without real children when possible.
