# Phase 4 — RFID reader registration and secure ingest

Phase 4 adds hardware-authenticated RFID event ingestion without attendance calculation.

## Architecture

- **Human APIs** (`/api/v1/...`) continue to use JWT + tenant membership + RLS.
- **Ingest** (`POST /ingest/v1/rfid/events`) uses device HMAC authentication; tenant is resolved from `rfid_devices`, never from the request body.
- **Device directory** (`rfid_devices`, `rfid_device_keys`) has no RLS and stores no student PII. Signing secrets are Fernet-encrypted at rest (`secret_encrypted`), not password hashes.
- **Tenant tables** (`rfid_readers`, `rfid_events`, `rfid_event_processing`, `rfid_observations`, `rfid_ingest_rejects`) use FORCE RLS.

## Flow

1. Validate signed request (headers, skew, signature, nonce, rate limit).
2. Resolve device → `tenant_id`, `reader_id`.
3. `SET LOCAL` tenant context (`actor_type=device`).
4. Persist immutable `rfid_events` (idempotent on `tenant_id + reader_id + device_event_id`).
5. Create `rfid_event_processing` and `rfid_observations` (card resolution as-of `occurred_at`).
6. No attendance records.

## Security

See `docs/rfid-ingest.md` for the hardware protocol.

## Tests

- `tests/test_rfid_readers.py`
- `tests/test_rfid_devices.py`
- `tests/test_rfid_ingest.py`

## Open hardware questions

- Exact UHF reader firmware event schema variants (optional fields).
- Whether readers can supply sub-second `occurred_at` reliably.
- On-device clock sync strategy in production.
