# UHF RFID architecture

**Status:** Architecture only. Production path is **real readers**. A card EPC is not the student.

School entry/exit uses **UHF (typically EPC Gen2)** at range. HF/NFC is documented in [nfc.md](nfc.md). Identity model: [database.md](database.md).

---

## Layers (non-negotiable)

```
1. Raw RFID event          immutable, auditable (rfid_events)
2. Processing / dedup      mutable status (rfid_event_processing)
3. Attendance observation  append-only detection fact
4. Derived attendance      product record (reports, parents)
```

**An RFID POST must not write “student present” in one step.** Ingest only accepts or rejects **raw** events. Matching, debounce, and attendance happen in processing.

An administrator must be able to answer: *this attendance_record ← observation ← processing row ← raw event + reader + assignment*.

---

## 9. Decision: HTTPS device ingest + durable raw events + async derivation

1. Admin registers a **reader** on a **gate** (`in` / `out` / paired), tenant-scoped, `status=active|disabled`.
2. Reader or **edge agent** POSTs to `https://ingest…/ingest/v1/rfid/events` with device credentials.
3. Ingest authenticates device, resolves **tenant from device directory** (not from body), validates, **INSERT raw event**, outbox `rfid.received` (`tenant_id`, `rfid_event_id` only).
4. Worker sets RLS GUCs from the message, loads the event, matches **physical card + assignment as of `occurred_at`**, dedupes, writes observation ± derived record, outbox `notify.send` if a new parent-visible record is created.

```
UHF reader ──HTTPS──► ingest-api ──► rfid_events (immutable)
                         │
                         └─ outbox ─► Service Bus ─► attendance worker
                                      ├─ rfid_event_processing
                                      ├─ attendance_observations
                                      ├─ attendance_records
                                      └─ notify.send (ids only)
```

### Why / alternatives / tradeoffs / scale / cost

Gates burst duplicate reads. Raw vs derived keeps disputes honest and keeps FCM off the ingest path. IoT Hub/MQTT can be an **adapter** later. Processing inside the HTTP request couples reader timeouts to FCM. Scale: write-optimized ingest; partition `rfid_events`. Cost: Postgres IOPS at bell time.

---

## Raw event fields (logical)

| Field | Role |
| --- | --- |
| `id` | Server event id (UUID) |
| `tenant_id` | From registered reader, never trusted from body |
| `reader_id` / `gate_id` | Hardware + portal |
| `device_event_id` | Reader-stable event id (duplicate detection) |
| `occurred_at` | Reader/agent time of the read |
| `received_at` | Server time at accept |
| `uhf_epc` / `uhf_tid` | Tag identifiers (not student PK) |
| `antenna` / `rssi` | RF context |
| `direction_hint` | Optional; authoritative direction from gate config |
| `signature_kid` | Which device key verified the POST |
| `nonce` | Replay uniqueness with timestamp |
| `ingest_status` | `accepted` only if persisted as raw |

Rejected requests **do not** become attendance. They may be logged in `ingest_rejects` (reader_id if known, reason, correlation_id) without storing full tag lists in App Insights.

---

## Ingest rejection (before or without raw persist)

| Condition | HTTP | Notes |
| --- | --- | --- |
| Unknown `device_id` / cert | 401 | |
| Disabled or revoked reader | 403 | |
| Invalid HMAC/mTLS signature | 401 | |
| Malformed JSON / missing required fields | 422 | |
| Duplicate `device_event_id` for reader | 200 | Idempotent; return original `id` |
| Replayed nonce+timestamp | 401/409 | |
| Clock skew on **signature timestamp** outside ±2 minutes | 401 | Buffered reads still send a fresh signature; **`occurred_at` may be older** |
| `occurred_at` > 15 minutes in the future | 422 | |
| Body `tenant_id` present and ≠ reader tenant | 403 | Tenant mismatch |
| Body `reader_id` ≠ authenticated reader | 403 | |

Signature timestamp skew ≠ discarding delayed `occurred_at`. Edge agents: unique `device_event_id` at read time, `occurred_at` from that moment, HTTP signed **now**.

---

## Authentication of hardware

- Readers **never** use user JWT.
- Baseline: HMAC (`X-Device-Id`, signature-timestamp, nonce, body hash) with key in Key Vault / device directory.
- Prefer mTLS when client certs can be installed.
- Tenant context: [architecture.md](architecture.md) §5 (`actor_type=device`).

---

## Processing / deduplication

Worker (idempotent on `rfid_event_id`):

1. Set `app.tenant_id` from message; abort to DLQ on mismatch.
2. Resolve card: prefer **TID** if bound, else EPC, among `physical_cards` for that tenant.
3. Resolve **assignment active at `occurred_at`** (`activated_at ≤ occurred_at` and (`revoked_at` is null or `revoked_at > occurred_at`)).
4. Unknown / no assignment: `process_status=unmatched`; admin alert; **no** observation for a student; **no** parent notify.
5. Direction: gate config, not time-of-day heuristics (see Direction section below).
6. Dedup: same `student_id` + `gate_id` + direction within N seconds (default 60–120, per tenant) → observation with `debounce_of_observation_id`, **no second** derived `attendance_records`, **no second** notify.
7. Else: insert observation `kind=school_in|school_out`, then derived record, then `notify.send`.

Anti-passback: optional entitlement; default **off**.

---

## Direction (entry vs exit)

| Method | When |
| --- | --- |
| Two readers or antennas configured `in`/`out` | Preferred |
| Time of day as sole method | **Forbidden** |
| RSSI sequence | Vendor adapter only |

Single reader: school configures the gate as `in` or `out` (or day-part config), not guessed.

---

## Time and notifications

- Observation/record `occurred_at` from reader `occurred_at` after sanity.
- Notify uses first name + gate + time — **not** EPC, not a dossier. Inbox row before FCM ([notifications.md](notifications.md)).

---

## Reader health

`readers.last_seen_at` on accepted ingest or heartbeat. Alert if silent during configured `bell_windows`.

---

## Card issuance vs RFID

Admin issues `physical_cards` and `card_assignments`. Lost card: revoke assignment, activate replacement. Old EPC may still appear: unmatched or historical assignment if `occurred_at` is in the old window (delayed edge buffer). Processing uses **as-of** assignment, so delayed events stay interpretable.

---

## Vendor adapters

Canonical JSON only at ingest. Edge plugins convert Impinj/Zebra/OEM TCP.

---

## Lab vs production

Staging: real lab readers when possible. `hardware-sim` is local compose only. Production images have **no** generate-fake-EPC API.
