# Attendance engine

## Input

Only `rfid_observations` with `resolution_status = resolved` and a `student_id` are eligible.

## Direction

| Reader `direction_mode` | Effective signal direction |
|-------------------------|----------------------------|
| `entry` | entry (ignores event direction) |
| `exit` | exit |
| `both` | requires event `direction` of entry or exit |

## Debouncing

Dedupe key: `{student_id}:{attendance_date}:{direction}:{floor(epoch/dedupe_seconds)}`.

Separate windows: `entry_dedupe_seconds`, `exit_dedupe_seconds` on the active `attendance_policies` row for the local date.

## Attendance date

Computed from `observed_at` in the tenant's `tenants.timezone` (not UTC calendar date).

## Entry / exit aggregation

- **entry**: set `entry_at` to earliest valid signal; status from policy (`present` / `late`).
- **exit**: set `exit_at` to latest valid signal.

Ordering uses `occurred_at` / `observed_at`, not `received_at`.

## Worker

`attendance_observation_processing` rows are enqueued at RFID ingest. The worker sets tenant context per school and runs `process_pending_observations`.

## Finalization

`POST /api/v1/attendance/finalize` marks eligible enrolled students without entry as `absent` for a school day (not on weekends / configured non-school days).

## Corrections

`POST /api/v1/attendance/{id}/corrections` appends `attendance_corrections` and bumps record `version`; no silent PATCH on records.
