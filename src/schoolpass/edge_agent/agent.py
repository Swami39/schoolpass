"""Edge agent: reader TCP <-> SchoolPass ingest.

Pure helpers (``EdgeDedup``, ``build_event``, ``sign_request``) are kept
free of I/O so they are unit-testable. ``EdgeAgent`` wires them to the
network with an SQLite outbox for durable delivery.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from schoolpass.edge_agent.config import EdgeConfig
from schoolpass.rfid import security as rfid_security
from schoolpass.rfid.vendors import srk_idt98

log = logging.getLogger("schoolpass.edge_agent")

PERMANENT_HTTP_STATUS = {400, 401, 403, 404, 409, 422}


# --- pure helpers ----------------------------------------------------------


class EdgeDedup:
    """Suppress repeat sightings of the same EPC within a time window.

    A student walking through the gate keeps the tag in the field for
    seconds; the reader reports it dozens of times. The server also
    debounces, but dropping the flood at the edge keeps ingest (and its
    per-device rate limit) healthy.
    """

    def __init__(self, window_seconds: float) -> None:
        self._window = window_seconds
        self._last_seen: dict[str, float] = {}

    def seen(self, epc: str, *, now: float | None = None) -> bool:
        """Return True if this EPC was already reported inside the window."""
        now = time.monotonic() if now is None else now
        last = self._last_seen.get(epc)
        if last is not None and now - last < self._window:
            return True
        # opportunistic cleanup so the map cannot grow without bound
        if len(self._last_seen) > 10000:
            cutoff = now - self._window
            self._last_seen = {k: v for k, v in self._last_seen.items() if v >= cutoff}
        self._last_seen[epc] = now
        return False


def build_event(
    device_id: str,
    read: srk_idt98.TagRead,
    direction: str | None,
    *,
    occurred_at: datetime | None = None,
    device_event_id: str | None = None,
) -> dict:
    """Build one canonical ingest event body for a tag sighting.

    ``occurred_at`` is the moment the edge agent received the frame: the
    reader's binary protocol carries no per-read timestamp, so receive
    time is the most honest occurrence time available.
    """
    return {
        "device_event_id": device_event_id or uuid4().hex,
        "occurred_at": (occurred_at or datetime.now(UTC)).isoformat(),
        "uhf_epc": read.epc,
        "antenna": read.antenna,
        "rssi": float(read.rssi_dbm),
        "direction": direction,
        # not part of the canonical schema; kept for local debugging only
        "_edge": {"reader": device_id, "pc": f"{read.pc:#06x}"},
    }


def public_event(event: dict) -> dict:
    """Strip edge-local debug keys before POSTing."""
    return {k: v for k, v in event.items() if not k.startswith("_")}


@dataclass(frozen=True)
class SignedRequest:
    url: str
    body: bytes
    headers: dict[str, str]


def sign_request(
    config: EdgeConfig, event: dict, *, nonce: str | None = None, timestamp: int | None = None
) -> SignedRequest:
    """Sign a canonical event per docs/rfid-ingest.md."""
    body = json.dumps(public_event(event), separators=(",", ":")).encode("utf-8")
    ts = str(int(time.time()) if timestamp is None else timestamp)
    nonce = nonce or secrets.token_hex(16)
    path = urllib.parse.urlsplit(config.ingest_url).path or "/"
    message = rfid_security.canonical_message(
        method="POST",
        path=path,
        timestamp=ts,
        nonce=nonce,
        body_hash=rfid_security.body_sha256_hex(body),
        device_id=config.device_id,
        key_version=str(config.device_key_version),
    )
    signature = rfid_security.compute_signature(config.device_secret, message)
    return SignedRequest(
        url=config.ingest_url,
        body=body,
        headers={
            "Content-Type": "application/json",
            "X-Device-Id": config.device_id,
            "X-Key-Version": str(config.device_key_version),
            "X-Timestamp": ts,
            "X-Nonce": nonce,
            "X-Signature": signature,
        },
    )


def post_signed(signed: SignedRequest, timeout: float) -> tuple[int, bytes]:
    """Blocking POST; run in a thread from async code."""
    req = urllib.request.Request(signed.url, data=signed.body, headers=signed.headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


# --- durable outbox --------------------------------------------------------


class Outbox:
    """SQLite outbox: persist-then-send, retry with the same device_event_id."""

    def __init__(self, path: str) -> None:
        self._db = sqlite3.connect(path)
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS outbox (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   device_event_id TEXT UNIQUE NOT NULL,
                   payload TEXT NOT NULL,
                   attempts INTEGER NOT NULL DEFAULT 0,
                   last_error TEXT,
                   created_at REAL NOT NULL)"""
        )
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS dead_letter (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   device_event_id TEXT NOT NULL,
                   payload TEXT NOT NULL,
                   error TEXT,
                   created_at REAL NOT NULL)"""
        )
        self._db.commit()

    def enqueue(self, event: dict) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO outbox (device_event_id, payload, created_at) VALUES (?, ?, ?)",
            (event["device_event_id"], json.dumps(event), time.time()),
        )
        self._db.commit()

    def oldest_pending(self) -> tuple[int, dict] | None:
        row = self._db.execute("SELECT id, payload FROM outbox ORDER BY id LIMIT 1").fetchone()
        if row is None:
            return None
        return row[0], json.loads(row[1])

    def pending_count(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]

    def mark_sent(self, row_id: int) -> None:
        self._db.execute("DELETE FROM outbox WHERE id = ?", (row_id,))
        self._db.commit()

    def mark_failed(self, row_id: int, error: str) -> None:
        self._db.execute(
            "UPDATE outbox SET attempts = attempts + 1, last_error = ? WHERE id = ?",
            (error, row_id),
        )
        self._db.commit()

    def mark_dead(self, row_id: int, error: str) -> None:
        row = self._db.execute("SELECT device_event_id, payload FROM outbox WHERE id = ?", (row_id,)).fetchone()
        if row:
            self._db.execute(
                "INSERT INTO dead_letter (device_event_id, payload, error, created_at) VALUES (?, ?, ?, ?)",
                (row[0], row[1], error, time.time()),
            )
            self._db.execute("DELETE FROM outbox WHERE id = ?", (row_id,))
            self._db.commit()

    def close(self) -> None:
        self._db.close()


# --- agent -----------------------------------------------------------------


class EdgeAgent:
    def __init__(self, config: EdgeConfig) -> None:
        self.config = config
        self.outbox = Outbox(config.outbox_db)
        self.dedup = EdgeDedup(config.dedup_window_seconds)
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        sender = asyncio.create_task(self._sender_loop(), name="outbox-sender")
        try:
            while not self._stop.is_set():
                try:
                    await self._reader_loop()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 - reconnect on any failure
                    log.warning("reader connection lost: %s", exc)
                if not self._stop.is_set():
                    await asyncio.sleep(self.config.reconnect_delay_seconds)
        finally:
            sender.cancel()
            try:
                await sender
            except asyncio.CancelledError:
                pass
            self.outbox.close()

    async def _reader_loop(self) -> None:
        cfg = self.config
        log.info("connecting to reader %s:%d", cfg.reader_host, cfg.reader_port)
        reader, writer = await asyncio.open_connection(cfg.reader_host, cfg.reader_port)
        parser = srk_idt98.FrameParser()
        try:
            if cfg.start_inventory_on_connect:
                cmd = srk_idt98.build_start_inventory(
                    q_value=cfg.q_value,
                    inv_number=cfg.inv_number,
                    address=cfg.reader_address,
                )
                writer.write(cmd)
                await writer.drain()
                log.info("started inventory (Q=%d, N=%d)", cfg.q_value, cfg.inv_number)
            while not self._stop.is_set():
                chunk = await asyncio.wait_for(reader.read(4096), timeout=30)
                if not chunk:
                    log.warning("reader closed the connection")
                    return
                for frame in parser.feed(chunk):
                    self._handle_frame(frame)
        finally:
            try:
                writer.write(srk_idt98.build_stop_inventory(address=cfg.reader_address))
                await writer.drain()
            except Exception:  # noqa: BLE001 - best effort on shutdown
                pass
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    def _handle_frame(self, frame: srk_idt98.Frame) -> None:
        if (frame.cmdh, frame.cmdl) == srk_idt98.CMD_STOP_MULTI:
            end = srk_idt98.parse_inventory_end(frame)
            if end:
                log.info("reader ended inventory run: %d tags", end.tag_count)
            return
        try:
            read = srk_idt98.parse_tag_read(frame)
        except ValueError as exc:
            log.warning("dropping malformed tag frame: %s", exc)
            return
        if read is None:
            return
        if not read.stored_crc_ok:
            log.warning("tag CRC mismatch for EPC %s...; keeping event", read.epc[:8])
        if self.dedup.seen(read.epc):
            return
        event = build_event(self.config.device_id, read, self.config.direction)
        self.outbox.enqueue(event)
        log.debug("enqueued EPC %s rssi=%d ant=%d", read.epc, read.rssi_dbm, read.antenna)

    async def _sender_loop(self) -> None:
        cfg = self.config
        while not self._stop.is_set():
            pending = self.outbox.oldest_pending()
            if pending is None:
                await asyncio.sleep(0.5)
                continue
            row_id, event = pending
            signed = sign_request(cfg, event)
            try:
                status, body = await asyncio.to_thread(post_signed, signed, cfg.post_timeout_seconds)
            except Exception as exc:  # noqa: BLE001 - network failure, retry later
                self.outbox.mark_failed(row_id, f"network: {exc}")
                await asyncio.sleep(cfg.retry_interval_seconds)
                continue
            if 200 <= status < 300:
                try:
                    duplicate = bool(json.loads(body or b"{}").get("duplicate"))
                except ValueError:
                    duplicate = False
                self.outbox.mark_sent(row_id)
                log.info("event %s accepted%s", event["device_event_id"][:8], " (duplicate)" if duplicate else "")
            elif status in PERMANENT_HTTP_STATUS:
                self.outbox.mark_dead(row_id, f"http {status}: {body[:200]!r}")
                log.error(
                    "event %s rejected permanently (http %d); moved to dead_letter",
                    event["device_event_id"][:8],
                    status,
                )
            else:
                self.outbox.mark_failed(row_id, f"http {status}: {body[:200]!r}")
                await asyncio.sleep(cfg.retry_interval_seconds)
