# Transport GPS (Phase 6C)

Bus trip GPS tracking: phone GNSS capture, offline buffering, batch sync, PostgreSQL history, Redis latest location. NFC boarding/drop-off semantics are unchanged ([transport-nfc.md](transport-nfc.md)).

Mobile package: [`apps/mobile/attendant_nfc/`](../apps/mobile/attendant_nfc/) (`GpsSampleService`, `GpsOutboxStore`, `GpsSyncWorker`).

---

## Architecture

```
Phone GNSS → GpsAdapter → GpsSampleService → SQLite gps_outbox
         → GpsSyncWorker (batch) → POST /api/v1/transport/gps/samples/sync
         → PostgreSQL location_samples (history)
         → Redis trip:{trip_id}:last (latest only, in_progress trips)
```

- **PostgreSQL** is durable history (source of truth).
- **Redis** holds only the latest fix per active trip; history must not depend on Redis.
- **Server** derives tenant, attendant, and bus from auth + trip; clients must not send `tenant_id`.

---

## Trip association and phases

| Trip status | Live capture | Delayed upload (`occurred_at` in window) |
| --- | --- | --- |
| `in_progress` | Accepted | Accepted |
| `completed` | Rejected (phase) | Accepted if `[started_at, ended_at]` |
| `scheduled`, `boarding` | Rejected | Rejected |
| `cancelled` | Rejected | Rejected |

Window is inclusive `[started_at, ended_at]`; `ended_at` NULL means no upper bound while the trip is open.

Attendant must own the trip; optional `bus_id` in the payload must match the trip’s bus when provided.

---

## Idempotency

Logical key: **`(client_device_id, client_sample_id)`** (header + body).

Retries must reuse the same `client_sample_id`, `occurred_at`, coordinates, and `device_sequence`.

---

## Device sequence

The attendant local SQLite `device_meta` key `device_sequence` is **shared with NFC** when both outboxes use the same database file. One monotonic per-device sequence across event types.

---

## Batch sync API

**POST** `/api/v1/transport/gps/samples/sync`

- Header: `X-Client-Device-Id`
- Body: `{ "samples": [ ... ] }` (1–50 items)
- Response: per-sample `processed` | `duplicate` | `rejected`

**GET** `/api/v1/transport/gps/trips/{trip_id}/samples` — recorded history (`gps_samples:read`), for ops/testing; not parent-facing.

---

## Redis latest location

Key: `trip:{trip_id}:last`

JSON fields: `trip_id`, `bus_id`, `latitude`, `longitude`, `occurred_at`, `received_at`, optional `accuracy_meters`. No student PII.

Updated only when:

1. Sample is **recorded** in PostgreSQL, and  
2. Trip is **`in_progress`**, and  
3. Sample `occurred_at` is **newer** than the cached value.

Redis failures after commit are logged; PostgreSQL rows are not rolled back.

---

## Mobile buffering

- Explicit sync states: `pending`, `syncing`, `processed`, `duplicate`, `rejected`
- Crash recovery: `syncing` → `pending` on startup
- **Batch** upload (default max 50), not NFC-style single-event drain
- [`GpsSamplingPolicy`](apps/mobile/attendant_nfc/lib/src/gps_sampling_policy.dart): configurable interval, distance, accuracy (pilot defaults: 15s, 25m, 50m desired accuracy)

---

## Privacy and retention

- Do not log raw coordinates in application logs or audit payloads by default.
- Product retention (jobs not in this phase): **7 days** detailed samples, **90 days** 1-minute downsample, then delete coordinates ([gps.md](gps.md)).

---

## Source field

`phone_gnss` (pilot). Schema allows future `hardware_tracker` without a history redesign.

---

## Rejection codes (GPS)

Includes: `invalid_latitude`, `invalid_longitude`, `invalid_accuracy`, `invalid_speed`, `invalid_heading`, `invalid_trip`, `cancelled_trip`, `invalid_event_window`, `invalid_trip_phase`, `unauthorized_attendant`, `bus_mismatch`, plus shared device codes from transport auth.

NFC rejection semantics are unchanged.
