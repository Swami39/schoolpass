# GPS and bus tracking architecture

**Status:** Architecture only. Production locations come from **real GNSS** (attendant app) and/or **certified vehicle trackers**.

Drop-off is **NFC / explicit attendance**, not inferred from geofencing alone ([nfc.md](nfc.md)).

---

## Storage boundaries

| Store | Holds | Does not hold |
| --- | --- | --- |
| **Redis** | Current/latest position for the **active trip**; short TTL live state (accuracy, source, `occurred_at`) | Historical polyline; anything a parent must see after Redis flush |
| **PostgreSQL** | `trips` metadata and lifecycle; `trip_transitions` (geofence enter/exit); **required** historical `location_samples` (downsampled) | Sub-second junk; 24/7 attendant tracking off-trip |

**Historical GPS must not depend on Redis.** A replica flush or cache eviction may affect **live** UI freshness only. Polyline and “where was the bus at 07:52” are served from Postgres (and then optionally cached).

Service Bus: **not** every sample. Only `trip.lifecycle` and `trip.geofence` ([architecture.md](architecture.md) §15). Sessions: `session_id = bus_id` for those topics so enter/exit order per bus is preserved.

---

## 11. Decision: trip-scoped GNSS; phone for pilot; tracker adapter; adaptive sampling

```
Attendant app / tracker
  ├─ if trip active: POST GPS batch (or ingest hardware)
  ├─ API: validate trip + actor
  ├─ Redis SET trip:{id}:last
  └─ Postgres INSERT location_samples if downsample policy says persist
Parent GET last: Redis (fallback PG last sample) after RBAC
Parent GET polyline: Postgres only
```

**Pilot default:** Flutter GNSS **only while `trips.status=active`**, with OS disclosure and consent copy.

**Hardware adapter:** `POST /ingest/v1/gps/samples`, IMEI bound to `buses.tracker_imei`. Same tables, `source=hardware|phone`. If both: display the fresher `occurred_at` within 30s; else hardware if phone stale.

Client map SDK: **Google Maps** with restricted keys; **coordinates only from SchoolPass API** (decision index).

### Why / alternatives / tradeoffs / scale / cost

Parents need “is the bus near the stop.” Phone GNSS unblocks 1–10 schools before vehicle installs. 1 Hz to all parents is a privacy and cost failure. At 10k buses, persist 30–60s samples; Redis every 5s. Map tiles and accidental logging of streams are the cost/risk meters.

---

## Trip lifecycle

| Status | Meaning | GPS |
| --- | --- | --- |
| `scheduled` | Assigned attendant, bus, route, service_date | **Off** |
| `active` | Attendant (or system) started trip; `started_at` set | **On** — only authorized trip |
| `completed` | `ended_at` set | **Off**; Redis key expires |
| `cancelled` | Never ran | **Off** |

Start/stop are authenticated attendant (or school_admin override) commands, or hardware ignition rules later. Offline start/stop: immutable client events; server idempotent.

Invariant: **no GPS collection when the trip is not active** (device must not send; server **rejects** samples for non-active trips except late samples with `occurred_at` inside `[started_at, ended_at]` after completion — those persist to history, do not reopen live tracking).

We track the **trip/bus**, not the attendant as a person 24/7.

---

## Adaptive sampling

| Condition | Device send | Persist to Postgres |
| --- | --- | --- |
| Moving, on trip | every 5s | every 30–60s or on heading/speed change |
| Stopped > 2 min | every 30s | on stop/start transition + 1-min |
| Offline | outbox with `occurred_at` | on sync, same downsample |
| Impossible speed | send with flag | persist `flagged`; exclude from parent polyline until review |

---

## Offline GPS

Same client-event/outbox mechanism as NFC. `occurred_at` is the GNSS fix time; `received_at` is sync time. After sync, history polyline updates; Redis last position updates if this fix is newer than current last for the trip.

---

## Timestamp semantics

- `occurred_at`: GNSS/device time of the fix (UTC).
- `received_at`: server.
- Parent “2 min ago” uses `occurred_at` of last **authorized** sample, not server clock alone.
- Stale: if `now - occurred_at` > 10 minutes during `active` trip → UI warning, not a fake live marker.

Accuracy: store `accuracy_m`. Do not imply survey-grade precision.

---

## Authorization and isolation

| Actor | Sees |
| --- | --- |
| Parent | Buses/trips for **their** children via `student_guardians` + `transport_assignments` (and active/recent trip). **Not** the fleet. |
| Attendant | Own **assigned** active/scheduled trip only |
| Teacher | **No** GPS in v1 |
| School admin | School fleet (RBAC `bus:track_school`) |
| Other tenant | Nothing (RLS) |

File/API: parent `GET` with another tenant’s `trip_id` → **404**. Release-blocking test.

---

## Geofences

Campus and `stops.geofence_radius_m` (default 80–120 m). Worker (from persisted samples or on-write check) records `trip_transitions`. Notify “approaching stop” throttled per child per trip. Hysteresis to prevent flicker.

**Drop-off is not a geofence fact.** `bus_alight` NFC or explicit attendant action creates the attendance observation.

---

## Retention and privacy

Product + minimization: 7 days high-frequency samples; 90 days 1-minute downsample; then **delete coordinates**. Unchanged in spirit from the original architecture. Not a legal claim. No sale of location. No analytics SDKs consuming GNSS. Do not log GPS streams by default ([security.md](security.md)).
