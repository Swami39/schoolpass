# NFC / HF architecture

**Status:** Architecture only. Production scanning uses **device NFC hardware** (or an approved external reader).

HF on the dual-frequency **physical card** is short-range (bus attendant, teacher fallback). UHF gates: [rfid.md](rfid.md). Cards are not students: [database.md](database.md).

**UID-only NFC is not unclonable and is not cryptographically secure.** Clone risk is operational (photo check, revoke, duplicate UID alerts). Profiles `ntag_sig` and `desfire` are supported on `physical_cards.profile` without changing student identity.

---

## 10. Decision: immutable client events; server authoritative

Flutter reads UID (and later secure app data) via NFC APIs. Writable NDEF `student_id=...` is **never** authorization.

Offline is mandatory. Local roster match is UX only.

### Why / alternatives / tradeoffs

UHF portals are not in the aisle. CRDTs / Firebase offline DBs are a second system of record. In-memory queues lose scans. DESFire from day one is a card-cost SKU, not a schema rewrite.

iOS: foreground scan session only. Apple NFC entitlement is a launch prerequisite.

---

## Immutable client event (logical fields)

Persisted on device **before** success UI, then uploaded unchanged (server may add server-only columns).

| Field | Set by | Meaning |
| --- | --- | --- |
| `client_event_id` | Device (UUID) | Idempotency with `device_id` |
| `device_id` | Registered client device | Revocable |
| `actor_user_id` | Session | Attendant or teacher |
| `tenant_id` | Session membership | Server re-checks; mismatch → reject |
| `type` | Device | `bus_board` \| `bus_alight` \| `class_nfc` \| `gps_sample` (GPS may batch separately) |
| `card_hf_uid` | NFC read | Identifier **on the card**, not student PK |
| `physical_card_id` | Optional local resolve | Hint |
| `student_id_local` | Optional local roster | Hint; **not** authoritative |
| `trip_id` / `bus_id` | Open trip context | Required for bus types |
| `device_seq` | Monotonic per device | Ordering aid; gaps allowed |
| `occurred_at` | Device clock UTC | **Authoritative occurrence time** after sanity |
| `received_at` | Server | When accepted |
| `sync_attempt_count` | Device | Diagnostics |
| `processing_state` | Server | `received` \| `accepted` \| `duplicate` \| `rejected_*` \| `unresolved` |
| `observation_id` | Server | If an observation was created |

Payload is append-only. The device does not edit `occurred_at` after first persist.

### Timestamp example

- Student scans at **08:30** (`occurred_at`).
- No network.
- Server receives at **09:10** (`received_at`).
- Boarding time is **08:30**. Parent copy and reports use 08:30. `received_at` is for SLA/sync-lag metrics and fraud review.

---

## Idempotency and conflict resolution (deterministic)

1. Unique `(device_id, client_event_id)`: replay returns the **original** `processing_state` and ids (`200`). No second observation.
2. Same student + same trip + same `type` within debounce window (default 3 minutes board, configurable): new client event stored, `processing_state=duplicate`, `debounce_of` existing observation. **No last-write-win** of parent-visible attendance.
3. Conflicting types (board then alight): both can exist; product order is by `occurred_at`, not receive order.
4. Two devices (should not happen): different `device_id`s; server still debounce by student+trip+type+window.
5. Unknown UID: `unresolved`; **not** dropped; **not** success; no parent board notify.
6. Validation failure: `rejected_wrong_bus` / `rejected_unauthorized_attendant` / `rejected_no_trip` / `rejected_tenant` / `rejected_clock`; event **retained**.

---

## Server validation (authoritative)

On first accept of a bus NFC event, with RLS `app.tenant_id` from the **user JWT**, not from the payload:

1. Membership: actor is attendant (or teacher for class types) for that tenant.
2. `tenant_id` on payload if sent must equal JWT `tid`.
3. Card: `physical_cards.hf_uid` for tenant; profile-specific checks later (DESFire).
4. Assignment **valid at `occurred_at`**.
5. Student `tenant_id` equals context tenant (invariant 1).
6. Open **trip** `id=trip_id`, `status=active` at `occurred_at` (or `scheduled` overlapping service_date if start was delayed — **decision: require trip `active` or `started_at ≤ occurred_at` and `ended_at` null or `> occurred_at`**). Offline: trip must have been downloaded; if trip already `completed` on server before delayed sync, still accept if `occurred_at` is within `[started_at, ended_at]` (inclusive window). If `occurred_at` after `ended_at`: `rejected_no_trip` unless school_admin override.
7. Attendant `trips.attendant_user_id` = actor (or assigned backup). Else `rejected_unauthorized_attendant`.
8. `transport_assignments` for student + bus/route **as of `occurred_at`**. Else `rejected_wrong_bus`.
9. Clock sanity: future > 15 min → reject; older than 36 h → flag for admin, do not auto-accept without policy (store `rejected_clock` or `accepted_flagged`).

**Decision for late events > 36h:** persist `rejected_clock`; school_admin may **explicitly** accept (audited), which creates observation using original `occurred_at`.

Local roster never overrides 4–8.

---

## Trip context

GPS and NFC share `trips` ([gps.md](gps.md)). Attendant starts trip (online preferred). Offline start: client event `trip_start` with `occurred_at`; server creates/activates trip idempotently. NFC board without trip_id → `rejected_no_trip`.

Drop-off: **`bus_alight` NFC (or explicit attendant action)** — not geofence alone.

---

## Roster cache

Download: assigned students for the trip, display name, short-lived photo SAS, `hf_uid` **for this bus only**. Encrypted on device. Expires when trip completes or token revoked.

---

## Teacher fallback

`type=class_nfc` or manual mark → observations/records with `source=nfc_teacher` | `manual_teacher`. Audited. Different source in reports — not a fake UHF gate.

---

## Security / cost / scale

Encrypted outbox. Logs: hash/truncate UID. Volume ≪ UHF. DESFire = entitlement and card stock, same event schema (`profile` + optional cryptogram field later).
