# Mobile NFC outbox (Phase 6B.3)

Bus attendant **offline-first** NFC scans. Server contract and business rules: [transport-nfc.md](transport-nfc.md). HF UID normalization: [nfc.md](nfc.md).

Implementation: [`apps/mobile/attendant_nfc/`](../apps/mobile/attendant_nfc/).

## End-to-end flow

```
NFC hardware → NfcAdapter (normalized UID)
            → NfcEventService (trip context, device_sequence, client_event_id)
            → SQLite outbox (pending)
            → NfcSyncWorker when online
            → POST /api/v1/transport/nfc/events/sync
            → processed | duplicate | rejected persisted locally
```

The scan is **accepted locally** only after the outbox row is committed. Server success is **not** required for local acceptance.

## Outbox record

Each row holds: `client_event_id`, `client_device_id`, event fields (`event_type`, `card_uid`, `trip_id`, optional `trip_stop_id`, `occurred_at`, `device_sequence`), `created_at`, sync metadata (`sync_state`, `attempt_count`, `last_attempted_at`, `last_error`, `rejection_code`), and server acknowledgement (`server_event_id`, `boarding_record_id`, `acknowledged_at`).

No student PII and no secrets in the outbox.

## Sync state machine

| State | Meaning |
| --- | --- |
| `pending` | Waiting for sync (or retry after transient failure) |
| `syncing` | Claimed by the worker; request in flight or crash window |
| `processed` | Server accepted and created/linked business record |
| `duplicate` | Idempotent replay (`client_device_id`, `client_event_id`) |
| `rejected` | Server business rejection **or** non-retryable HTTP/client failure |

Transient failures (network, timeout, 5xx, unexpected body) return the row to **`pending`**. Business **`rejected`** responses from the API are terminal. Rows are **not** deleted after rejection.

## Idempotency

- **`client_event_id`**: UUID generated once at scan time; **unchanged** on every retry.
- **`occurred_at`** and **`device_sequence`**: immutable after insert; retries send the same values.
- Server idempotency key: `(client_device_id, client_event_id)` (header + body).

## `device_sequence`

Monotonic counter in SQLite (`device_meta`), incremented inside the same transaction as outbox insert. Survives app restart; not derived from queue length or timestamps.

## Trip context

`NfcEventService` requires an active [`TripSelection`](../apps/mobile/attendant_nfc/lib/src/trip_context.dart). Without it, **`NoActiveTripError`** — no outbox row is written.

Optional `trip_stop_id` comes from current stop context when the app has one; server validates stop correctness.

## Crash recovery

On worker startup, `recoverOnStartup()` moves **`syncing` → `pending`** so events are not lost if the process dies after claim or mid-request.

Design is **at-least-once** delivery; the server remains authoritative for duplicates and validation.

## Retry semantics

| Condition | Behavior |
| --- | --- |
| Network / timeout / 5xx | Return to `pending`, bounded attempts |
| 401 / 403 | Terminal `rejected`, `last_error` `auth_*` (re-auth / device config) |
| Other 4xx without sync body | Terminal `rejected`, `last_error` `http_*` |
| 200 + `result: rejected` | Terminal `rejected`, server `rejection_code` stored |

Do not weaken server validation because the device validated locally.

## Server authority

Tenant and attendant identity come from the **JWT** and **`X-Client-Device-Id`**. The mobile sync JSON must **not** include `tenant_id`.

## Concurrency

One ordered worker; `claimNextPending()` uses `BEGIN IMMEDIATE` so two workers cannot claim the same pending row.

## Tests

`dart test` in `apps/mobile/attendant_nfc` covers outbox durability, sync outcomes, recovery, ordering, trip guard, UID normalization, and payload shape (no `tenant_id`).
