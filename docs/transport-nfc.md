# Transport NFC bus attendance (Phase 6B.1–6B.2)

Server-side foundation for mobile NFC sync. See also [nfc.md](nfc.md). Mobile outbox and offline sync (Phase 6B.3): [mobile-nfc-outbox.md](mobile-nfc-outbox.md).

## Event vs boarding record

- **Client event** (`client_events`): immutable device payload — `client_event_id`, `device_sequence`, **`occurred_at`**, normalized `card_uid`, and client-supplied `trip_id` (not FK-enforced so invalid ids still persist as rejections).
- **Transport boarding record** (`transport_boarding_records`): validated outcome with composite FKs to trip, student, assignments, and client event.

A scan is an event; boarding/drop-off facts are created only after validation.

## Idempotency

Unique `(client_device_id, client_event_id)`.

| Retry outcome | `result` | Side effects |
| --- | --- | --- |
| Prior success | `duplicate` | No new boarding, audit, or outbox |
| Prior business rejection | `rejected` | No new audit or outbox |
| First success | `processed` | One boarding record, one audit, one outbox |

Concurrent duplicate inserts race on the unique constraint; one writer wins.

## Timestamps

- **`occurred_at`**: client scan time; drives card assignment, transport assignment, trip window, and dropoff sequence checks. Never overwritten by the server.
- **`received_at`**: server receipt time when the client event row is first inserted.

Delayed offline sync: a scan at 09:30 on a 09:00–10:00 trip is validated at 09:30 even if `received_at` is 12:00.

## Trip occurrence window

Semantics: **`occurred_at` must fall in `[started_at, ended_at]` inclusive** when `ended_at` is set. When `ended_at` is null, there is no upper bound (trip still active).

Rejections:

| Condition | Code |
| --- | --- |
| Trip `cancelled` | `cancelled_trip` |
| `started_at` is null (never started) | `trip_not_started` |
| Before `started_at` or after `ended_at` | `invalid_event_window` |

## Trip phase (current status vs event type)

After the occurrence window passes, current trip **status** gates event type (sync time status; historical completion is allowed when window matches):

| Event | Allowed statuses (after window OK) |
| --- | --- |
| **boarding** | `boarding`, `in_progress`, `completed` (not `scheduled`) |
| **dropoff** | `in_progress`, `completed` (not `scheduled` or `boarding`) |

Live dropoff while trip is still `boarding` → `invalid_trip_phase`.

## Boarding / dropoff sequence

- **Multiple boarding** events (different `client_event_id`) are allowed.
- **Dropoff** requires at least one **boarding** record for the same `(trip, student)` with `occurred_at <=` dropoff `occurred_at`. Otherwise → `boarding_required`.
- No time-based debounce; close-in-time scans with different event ids are independent.

## Card resolution (at `occurred_at`)

UID → `physical_cards` → `card_assignments` → student via `resolve_card` / `assignment_as_of`.

| Outcome | Code |
| --- | --- |
| Unknown UID | `unknown_card` |
| Blocked card | `card_blocked` |
| Retired card | `card_retired` |
| No assignment at time | `card_unassigned` |

Historical replacement: old UID valid only while its assignment was active at `occurred_at`.

## Transport assignment (at event date)

`get_effective_transport_assignment` for `occurred_at` date — active status only (suspended/cancelled/expired excluded).

| Outcome | Code |
| --- | --- |
| No effective assignment | `no_transport_assignment` |
| Route ≠ trip route | `route_mismatch` |
| Stop ≠ assignment stop (when `trip_stop_id` sent) | `stop_mismatch` |

## Stop validation

When `trip_stop_id` is provided: must belong to the trip snapshot; assignment stop must match the trip stop’s `route_stop_id`. When omitted, stop match is skipped.

Invalid stop on trip → `invalid_stop`.

## Device / attendant

- JWT tenant + user; header `X-Client-Device-Id` must be an **active** device owned by the user.
- Trip must belong to tenant (RLS); trip `attendant_id` must match the user’s transport attendant row.
- Payload cannot override tenant, attendant, bus, or student identity.

Auth failures (device/header) → HTTP 401 with `invalid_device`.

## Rejection codes (business, retry-safe)

Stable codes returned in API `rejection_code`:  
`unknown_card`, `card_blocked`, `card_retired`, `card_unassigned`, `invalid_trip`, `cancelled_trip`, `trip_not_started`, `invalid_event_window`, `invalid_trip_phase`, `boarding_required`, `no_transport_assignment`, `route_mismatch`, `stop_mismatch`, `invalid_stop`, `unauthorized_attendant`.

Infrastructure failures propagate as HTTP 5xx; they do **not** persist a business rejection on the client event (transaction rolls back).

## Audit / outbox

| Outcome | Boarding | Audit | Outbox |
| --- | --- | --- | --- |
| Processed | 1 | `transport.boarding.recorded` | same topic |
| Business rejection | 0 | `transport.nfc.rejected` (idempotent key per client event) | `transport.nfc.rejected` |
| Duplicate replay | 0 new | 0 new | 0 new |

## Boarding record immutability

Created rows are not updated when cards, assignments, or routes change later.

## Sync API

`POST /api/v1/transport/nfc/events/sync` — permission `transport_nfc:sync` (bus attendant).

## UID pilot limitation

UID-only HF cards are not cryptographically unclonable; authorization is server-side rules, not UID secrecy.
