# RFID ingest protocol (SchoolPass)

Hardware vendors implement this contract against `POST /ingest/v1/rfid/events`.

## Endpoint

```http
POST /ingest/v1/rfid/events
Content-Type: application/json
```

No `Authorization: Bearer` header. Authentication is request signing only.

## Headers

| Header | Description |
|--------|-------------|
| `X-Device-Id` | Globally unique device identifier (string, no PII) |
| `X-Key-Version` | Active signing key version (integer) |
| `X-Timestamp` | Unix seconds for the **request** (not the tag read time) |
| `X-Nonce` | Unique per request (replay protection) |
| `X-Signature` | Lowercase hex HMAC-SHA256 |

## Canonical message

Newline-separated lines (no trailing newline):

```text
METHOD
PATH
TIMESTAMP
NONCE
SHA256_HEX(BODY)
DEVICE_ID
KEY_VERSION
```

Example:

```text
POST
/ingest/v1/rfid/events
1770000000
random-nonce
a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3
reader-device-001
3
```

- `METHOD` is upper case (`POST`).
- `PATH` is the path only (no query string): `/ingest/v1/rfid/events`.
- `SHA256_HEX(BODY)` is computed over the raw request body bytes.
- Signature: `HMAC-SHA256(secret, canonical_message)` as lowercase hex.

Compare signatures in constant time on the server.

## Timestamp rules

- Request timestamp must be within `RFID_REQUEST_MAX_SKEW_SECONDS` (default 300) of server time.
- JSON field `occurred_at` is when the tag was read at the reader; it is independent of `X-Timestamp`.

## Nonce rules

- Each `(device_id, nonce)` pair is stored in Redis with TTL `RFID_NONCE_TTL_SECONDS` (default 600) using atomic `SET NX`.
- Reusing a nonce returns `409` with code `replayed_request`.

## JSON body

Required:

- `device_event_id` (string, unique per reader for idempotency)
- `occurred_at` (ISO-8601 datetime with timezone)

Optional identifiers (at least one recommended):

- `hf_uid`, `uhf_epc`, `uhf_tid`, `antenna`, `rssi`, `direction`

Normalization (server-side, must match when resolving cards):

- HF UID: trim whitespace
- UHF EPC / TID: trim whitespace, uppercase

## Success response

```json
{
  "status": "accepted",
  "duplicate": false,
  "event_id": "uuid",
  "resolution_status": "resolved"
}
```

Duplicate retry (same `device_event_id` for the same reader):

```json
{
  "status": "accepted",
  "duplicate": true,
  "event_id": "uuid",
  "resolution_status": "resolved"
}
```

## Error codes

| HTTP | Code | Meaning |
|------|------|---------|
| 401 | `invalid_device_auth` | Missing/invalid device headers |
| 401 | `invalid_signature` | HMAC mismatch |
| 401 | `unknown_key_version` | Key not active for device |
| 401 | `expired_timestamp` | Clock skew |
| 403 | `device_blocked` | Device or reader blocked/retired |
| 404 | `unknown_reader` | Reader missing for device |
| 409 | `replayed_request` | Nonce reuse |
| 422 | `invalid_event_payload` | JSON/schema failure |
| 429 | `rate_limited` | Per-device ingest limit exceeded |

## Retry guidance

- Safe to retry the **same** event with the **same** `device_event_id`; server returns `duplicate: true`.
- Do **not** reuse the same nonce; generate a new nonce per HTTP attempt.
- Recalculate signature if body or headers change.
