# SRK-6GWL UHF reader integration (gate readers)

**Status:** Implemented (edge agent + protocol adapter). Reader hardware is
provisioned per school after the first customer closes.

The SRK-6GWL is an integrated UHF reader (865–868 MHz for India,
ISO18000-6C / EPC Gen2, up to ~9 m with its 9 dBi antenna, TCP/IP + WiFi +
RS-232). It speaks the IDT98-family binary protocol documented in the
vendor SDK (`"IoT UHF Reader & Module API Communication Protocol V3.0.0"`).

## How it fits the architecture

```
SRK-6GWL ──TCP (binary 0xAA frames)──► edge agent ──HTTPS (HMAC)──► /ingest/v1/rfid/events
   (school LAN)                        (school LAN box)              (ingest API)
```

- The reader **does not** talk to the ingest API directly. Its
  `HTTP Client (POST JSON)` mode exists, but the JSON schema is not
documented in the SDK, so the supported path is TCP + edge agent.
- The edge agent (`src/schoolpass/edge_agent/`) parses the reader's
  inventory frames, dedupes repeat sightings at the edge, and POSTs
  canonical signed events. A local SQLite outbox makes delivery durable:
an event is persisted before its first POST and retried with the **same**
  `device_event_id` (fresh nonce per attempt) until accepted.
- Protocol parsing lives in `src/schoolpass/rfid/vendors/srk_idt98.py`;
  tests in `tests/test_rfid_srk_idt98.py` use golden vectors from the
  vendor documentation.
- `occurred_at` is the moment the edge agent received the frame — the
  reader's binary protocol carries no per-read timestamp, so receive time
  is the most honest occurrence time available.

## 1. Register the gate, reader and device

Via the school-admin API (tenant-scoped):

1. Create the gate and the RFID reader on it (`direction_mode`: `in`,
   `out`, or `paired`). See [rfid.md](rfid.md).
2. Create an RFID **device** for the reader. The response includes the
   `device_id`, `key_version` and a one-time `signing_secret`.
3. Store the secret securely — it goes into the edge agent's environment
   (`DEVICE_SECRET`), never into the reader.

Suggested `device_id` convention: `{school-code}-gate-{n}-uhf-1` (e.g.
`dpsrkp-gate-1-uhf-1`). No PII in device identifiers.

## 2. Configure the reader (xReaderConfiger)

Using the vendor `xReaderConfiger` tool over LAN:

| Setting | Value |
| --- | --- |
| Network | Static IP on the school LAN (or WiFi); note the IP |
| Tag Data Output → Interface | `RJ45 (TCP/UDP)` |
| Reader → mode | `Pooling` / Active — reader streams inventory frames |
| ISO18000-6C Tag → MB Data | `EPC Only` (TID not needed for gate attendance) |
| RF → Region | `865–868 MHz` (India) |
| RF → Power | Start low (e.g. 20 dBm) and raise until the gate lane reads reliably without reading the corridor |
| Data filter | Enabled (reader-side duplicate suppression) |
| TCP Heart Beat | `150 s` (keeps the LAN connection alive) |

Keep the reader's web/TCP management port reachable from the edge-agent
box only, not from the internet.

## 3. Encode student cards

Each physical card's EPC must equal `physical_cards.uhf_epc`
(uppercase hex, no spaces) for the assignment created in SchoolPass.
Write EPCs with the vendor tool or the reader's write command, then verify
by reading the card back through the edge agent logs and matching it in
the admin card list. **The EPC is not the student** — it resolves via
`CardAssignment` as of `occurred_at` (see [database.md](database.md)).

## 4. Deploy the edge agent

Any small always-on box on the school LAN (mini PC / Raspberry Pi):

```bash
pip install -e /path/to/schoolpass   # or copy the machine image
cp edge.env.example /etc/schoolpass/edge.env   # fill in secrets
python -m schoolpass.edge_agent
```

Environment:

| Variable | Required | Description |
| --- | --- | --- |
| `READER_HOST` | yes | Reader LAN IP |
| `READER_PORT` | no | TCP port (default `9090`) |
| `READER_ADDRESS` | no | Reader device address (default `255` = broadcast) |
| `DEVICE_ID` | yes | From device registration |
| `DEVICE_SECRET` | yes | One-time signing secret |
| `DEVICE_KEY_VERSION` | no | Default `1`; bump on rotation |
| `INGEST_URL` | yes | e.g. `https://ingest.schoolpass.example/ingest/v1/rfid/events` |
| `START_INVENTORY_ON_CONNECT` | no | Send 0xC1 on connect (default `true`) |
| `INVENTORY_Q_VALUE` | no | Q value, default `4` |
| `DEDUP_WINDOW_SECONDS` | no | Edge dedup window, default `5.0` |
| `EDGE_DIRECTION` | no | `in` / `out` override; empty = use the gate's `direction_mode` server-side |
| `OUTBOX_DB` | no | SQLite path, default `edge_outbox.db` |
| `POST_TIMEOUT_SECONDS` | no | Default `10.0` |
| `RETRY_INTERVAL_SECONDS` | no | Default `5.0` |
| `RECONNECT_DELAY_SECONDS` | no | Default `5.0` |

### Direction

- **One reader per gate:** leave `EDGE_DIRECTION` empty. Direction comes
  from the gate's `direction_mode` in SchoolPass — never guessed from
  signal data.
- **Two readers per gate (in-lane / out-lane):** run one agent per
  reader with `EDGE_DIRECTION=in` and `=out` respectively.

## 5. Verify end to end

1. Walk a programmed card through the gate; the agent log shows
   `enqueued EPC ...`.
2. `POST /ingest/v1/rfid/events` returns `{"status":"accepted", ...}`
   and the agent logs `accepted`.
3. The raw event appears under the reader in the admin API; the worker
   resolves it to the student and creates the observation / attendance
   record (see [rfid.md](rfid.md)).
4. Pull the network cable for a minute, walk cards through, reconnect:
   events queued in `edge_outbox.db` are delivered with their original
   `device_event_id`s (server reports `duplicate: true` for replays).

## Operations

- **Reconnects:** the agent re-sends start-inventory on every reconnect.
- **Permanent rejections** (401/403/422 — e.g. wrong secret, unknown
  reader) go to the `dead_letter` table, not into an infinite retry loop.
  Check the secret / key version / reader status, then re-queue.
- **Rate limits:** ingest enforces a per-device limit; the edge dedup
  window (default 5 s) plus the reader's data filter keep a walking
  student to ~1 event per pass.
- **Key rotation:** rotate via the admin API, update `DEVICE_SECRET` +
  `DEVICE_KEY_VERSION` on the box, restart the agent.
- **Logs:** structured logs on stdout; ship them to your log collector.
  No student PII is logged — only EPC prefixes and signal data.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Agent connects but no frames | Reader not in Pooling/Active inventory mode; send start-inventory or enable it in the config tool |
| `dropped_bytes` climbing | Wrong reader port, or another client is consuming the TCP stream |
| HTTP 401 `invalid_signature` | `DEVICE_SECRET` / `DEVICE_KEY_VERSION` mismatch; re-register or rotate |
| HTTP 404 `unknown_reader` | Device not registered for this tenant, or reader disabled |
| HTTP 429 `rate_limited` | Dedup window too short or reader data filter off |
| Events accepted but unresolved | Card EPC not assigned to a student as of `occurred_at`; check card assignment |

## Protocol reference (for maintainers)

Frame: `AA AA | RA | LEN | CMDH CMDL | STATUS | DATA | CRCH CRCL`,
CRC-CCITT (poly 0x1021, init 0xFFFF). Inventory `0xC1` tag data:
`RSSI(1, signed dBm) | PC(2) | EPC((PC>>11)*2 B) | StoredCRC(2) | ANT(1)`
with `0x00 → ANT1`. The vendor doc's one `LEN=0x17` example is a typo
(the consistent value is `0x18`); the parser validates by CRC, not LEN.

Related: [rfid.md](rfid.md) (ingest pipeline), [rfid-ingest.md](rfid-ingest.md)
(device auth contract), [database.md](database.md) (card identity model).
