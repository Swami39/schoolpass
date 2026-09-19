# Transport NFC bus attendance (Phase 6B.1)

Server-side foundation for mobile NFC sync. See also [nfc.md](nfc.md).

## Event vs boarding record

- **Client event** (`client_events`): immutable device payload — what was scanned, `client_event_id`, `device_sequence`, and **`occurred_at`** (device time).
- **Transport boarding record** (`transport_boarding_records`): durable outcome after server validation — links trip, student, assignments, and the client event.

A scan is an event; boarding/drop-off facts are created only after validation.

## Idempotency

Unique `(client_device_id, client_event_id)`. Retries return the same processing outcome (`processed` → `duplicate` category; rejections stay `rejected`). One boarding record per client event.

## Timestamps

- **`occurred_at`**: authoritative for card assignment, transport assignment, and trip window checks. Never overwritten by the server.
- **`received_at`**: server receipt time for sync lag metrics.

## Historical card resolution

Card → assignment → student is resolved **as of `occurred_at`** via `assignment_as_of` (see `rfid/resolution.py`). Replacing a card does not rewrite past assignments; an old UID is valid only while its assignment was active at `occurred_at`.

## Trip validation

Validity uses the trip **occurrence window** (`started_at` … `ended_at`), not sync time. A trip may be `completed` on the server while a delayed offline event is still accepted if `occurred_at` falls in that window.

- **Boarding**: not allowed on `scheduled` (no `started_at` / before start); allowed in window when trip has left `scheduled`.
- **Dropoff**: requires trip past boarding-only state (`in_progress` or `completed` within window); not on `scheduled` or `boarding`.

`cancelled` trips reject all events.

## UID pilot limitation

UID-only HF cards are **not** cryptographically unclonable. Authorization is server-side assignment + transport rules, not UID secrecy.

## Sync API

`POST /api/v1/transport/nfc/events/sync` with JWT tenant context, header `X-Client-Device-Id`, and body: `client_event_id`, `event_type` (`boarding`|`dropoff`), `card_uid`, `occurred_at`, `device_sequence`, `trip_id`, optional `trip_stop_id`.

Permission: `transport_nfc:sync` (bus attendant). Parents and teachers cannot submit.

## Rejection and retry

Rejected events are stored with `processing_state` and `rejection_code`. Retries return the same rejection without duplicate side effects. Successful retries after processing return `duplicate` with the existing boarding record id.
