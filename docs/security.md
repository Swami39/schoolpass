# Security architecture

**Status:** Architecture only. Aligned with the hardening pass.

Covers authentication, RBAC, audit, encryption, data classification, logging restrictions, and children’s-data obligations. Infra perimeter: [infrastructure.md](infrastructure.md). Tenant GUCs: [architecture.md](architecture.md) §5.

SchoolPass stores **minors’ identity, attendance, live location, and payments**. Security is a product requirement.

---

## Data classification

| Class | Definition | Examples | Who / where |
| --- | --- | --- | --- |
| **PUBLIC** | Intended for the open internet | Marketing site copy, school logo **if** the school marks it public | CDN / public container only for these assets |
| **INTERNAL** | Ops data without child PII | Device directory (`device_id` → tenant, key version), feature flags, template keys | API, workers, Key Vault for secrets **not** this class |
| **CONFIDENTIAL** | School business data | Timetable, announcement text, staff employee codes, non-public config | Tenant-scoped APIs; RLS |
| **SENSITIVE_CHILD_DATA** | Identifies or locates a child | Legal name, photo, DOB, admission_no, attendance, **GPS history**, results, HF UID / UHF EPC, guardian links | Postgres + private Blob; RLS + relationship checks; minimized logs |
| **FINANCIAL** | Money movement | Invoices, payments, refunds, webhook bodies, receipts | Postgres (webhook encrypted), Blob receipts; verified webhooks only |
| **SECURITY_SECRET** | Credentials that grant access | Password hashes, OTP codes, refresh tokens, JWT signing keys, reader HMAC, FCM service account, PSP secrets, SAS | Key Vault / hashed columns; never logs; never client source |

**Minimum access:** least privilege RBAC + FORCE RLS + relationship checks (parent↔child, attendant↔trip). Classification is stored on `files.classification` and implied by table.

**Systems:**

- Redis: live GPS (SENSITIVE_CHILD_DATA, short TTL), rate limits, permission cache — not long-term child dossiers.
- Service Bus: identifiers only (INTERNAL metadata + UUIDs).
- App Insights: INTERNAL telemetry; **no** SENSITIVE payloads, FINANCIAL bodies, SECURITY_SECRET.
- FCM: minimized display strings (SENSITIVE first name + gate) — unavoidable channel exposure; no GPS coordinates.
- Google Maps: tiles; **not** our coordinate store.

---

## 6. Authentication architecture

### Choice

**First-party identity in FastAPI.**

- Email and/or E.164 phone.
- Passwords: argon2id. Parent **OTP login** is first-class (SMS vendor / ACS), not a bypass.
- **RS256 access JWT** 5–15 minutes; **opaque refresh** hashed in DB, rotated every use; reuse ⇒ revoke family.
- Web: refresh in Secure HttpOnly SameSite=Lax cookie on API domain; CSRF header on mutations.
- Mobile: Keychain/Keystore, not SharedPreferences.
- **MFA TOTP required** for `school_admin` and all `platform_*`. Optional teachers. Parents not required in v1; revisit after abuse.
- Device binding: `device_id` on refresh; admin/user revoke; attendant devices revocable (queued NFC then fails auth).

JWT: `sub`, `ver`, `roles`, `tid` (school sessions), `mfa`, `jti`. Platform tokens: no `tid`, `plat: true`. Parent with two schools: picker issues a new access token; refresh stays user-scoped.

Hardware does **not** use this path ([rfid.md](rfid.md)).

### Session lifecycle

Login → refresh family created → access JWT. Logout / password change / MFA reset / admin revoke: family revoked. Access JWT remains until expiry (short). Worker jobs do not use user JWTs.

### Why / alternatives / cost

Control residency and MFA. Auth0/Clerk: MAU + child data in another cloud. Entra External ID: revisit for Microsoft-standardized trusts. OTP SMS is the meter; rate-limit and lockout in Redis (abuse protection).

---

## 7. RBAC architecture

Roles via `tenant_memberships`. Permissions `resource:action`. Entitlements (plan limits) are orthogonal.

| Role | Tenant | Scope |
| --- | --- | --- |
| `platform_super_admin` | none | Platform; impersonate (audited) |
| `platform_support` | none | Limited impersonation; no refunds |
| `platform_billing` | none | Plans, rail B |
| `school_admin` | school | School config except platform billing |
| `school_finance` | school | Fees/receipts; not device admin |
| `teacher` | school | Assigned divisions |
| `bus_attendant` | school | Assigned trips/NFC/GPS |
| `parent` | school | Authorized children only |

Enforcement: JWT role for `tid` → FastAPI `require()` → relationship filters → **FORCE RLS**. UI hiding is not security.

Deny by default. New routes without `require()` fail CI. Impersonation: `audit_logs` `tenant.impersonate` then `SET LOCAL app.tenant_id`.

---

## 17. Audit architecture

Append-only `audit_logs`: people, cards/assignments, devices, fees, results publish, login success/failure (**no passwords/OTP**), impersonation, exports, attendance corrections.

Redacted diffs; **no GPS trails** in audit (“viewed live location for student {id}”). RFID raw table is the hardware audit; assignment revoke is in `card_assignments` + audit.

Insert-only for `schoolpass_app`. Retention: [architecture.md](architecture.md) §25 (product default, not legal advice). Optional WORM blob after pilot.

---

## 19. Controls

### Transport and edge

TLS 1.2+, HSTS, Front Door WAF, ingest hostname separate, CORS allowlists, no `*`.

### Application

Pydantic, parameterized SQL, rate limits (auth/OTP/ingest/GPS poll/exports), idempotency keys, upload sniff + Defender, no user-defined webhook URLs.

### Secrets

Key Vault + workload identity. Rotate reader HMAC and PSP webhook secrets. No secrets in Flutter.

### Encryption

| Data | At rest | In transit | Extra |
| --- | --- | --- | --- |
| Postgres | Azure disk encryption | TLS | Webhook payloads encrypted column |
| Blob | Service encryption | HTTPS | Private containers |
| Backups | Encrypted | | Access audited |
| Mobile outbox | SQLCipher | TLS | |
| JWT / HMAC keys | Key Vault | | |

No Aadhaar. UID/EPC = SENSITIVE_CHILD_DATA, not public APIs.

### Logging and observability restrictions

Every request/worker: `correlation_id` / `request_id` (`X-Request-Id`), `tenant_id`, `actor_type`, `app.user_id` when set. OpenTelemetry traces. Metrics as in [infrastructure.md](infrastructure.md).

**Prohibit wholesale logging of:**

- Student dossiers (names + photos + ids dumps)
- Payment / webhook payloads
- Notification title/body/data payloads
- Authentication secrets, OTP, password hashes
- Access and refresh tokens
- GPS streams / coordinate lists (unless a **time-boxed diagnostic flag**, default off, SENSITIVE, operators MFA)

Log identifiers, error codes, counts.

### Abuse protection

Redis: OTP 5/15 min per phone; login lockout; ingest per reader; parent GPS 30/min; export 10/hour. WAF for volumetric. Step-up MFA on new device for admins.

### Privacy / law

DPDP: schools often fiduciary; SchoolPass **processor** in contract. Product: consent copy, export, offboarding, GPS minimization. **Do not claim** a retention number is legally mandatory ([architecture.md](architecture.md) §25). EU/US regimes: later, `data_residency` already on tenant.

### Threat model (abbreviated)

| Threat | Mitigation |
| --- | --- |
| Cross-tenant read | FORCE RLS + JWT `tid` + tests |
| Stolen parent token | Short JWT, rotation, device revoke |
| Cloned HF UID | Not claimed secure; photo; DESFire later |
| RFID replay | Nonce + signature skew + device_event_id |
| Wrong bus NFC | Server assignment as-of |
| Fake payment | Signature; ignore client success |
| Insider platform | MFA, impersonation audit, no BYPASSRLS in app |
| GPS stalking | Relationship + trip scope |
| Blob enumeration | Authz on `files.id`, not key |

---

## Secure development

Dependabot, gitleaks, no prod debug, no Playwright vs production, no session-replay SDKs on child screens, no photos in analytics vendors.
