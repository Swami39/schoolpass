"""Tests for the SRK-6GWL / IDT98 protocol adapter and the edge agent.

Golden vectors come straight from the vendor documentation
("IoT UHF Reader & Module API Communication Protocol V3.0.0",
"Reader 86L_98L configuration manual").

Note: one tag-report example in the vendor doc carries LEN=0x17 for a
24-byte LEN region (a doc typo; the consistent value is 0x18 as in the
other example). The parser validates frames by CRC, not by trusting LEN.
"""

from __future__ import annotations

import json

import pytest

from schoolpass.edge_agent.agent import EdgeDedup, Outbox, build_event, public_event, sign_request
from schoolpass.edge_agent.config import EdgeConfig
from schoolpass.rfid import security as rfid_security
from schoolpass.rfid.vendors import srk_idt98
from schoolpass.rfid.vendors.srk_idt98 import FrameParser, TagRead

pytestmark = pytest.mark.unit

# AA AA FF 08 C1 00 05 00 BC 44 4C  (QV=5, InvNumber=188)
HOST_START_INVENTORY = bytes.fromhex("AA AA FF 08 C1 00 05 00 BC 44 4C")
# AA AA FF 18 C1 00 00 BC 30 00 E2 00 30 09 28 11 01 46 11 20 A5 20 23 98 00 4D 56
TAG_FRAME_1 = bytes.fromhex("AA AA FF 18 C1 00 00 BC 30 00 E2 00 30 09 28 11 01 46 11 20 A5 20 23 98 00 4D 56")
# AA AA FF 18 C1 00 00 C9 30 00 11 22 33 44 55 66 77 88 99 00 AA BB 01 0B 00 B1 7F
TAG_FRAME_2 = bytes.fromhex("AA AA FF 18 C1 00 00 C9 30 00 11 22 33 44 55 66 77 88 99 00 AA BB 01 0B 00 B1 7F")
# AA AA FF 06 C1 00 15 8E C0  (inventory tag timeout)
TIMEOUT_FRAME = bytes.fromhex("AA AA FF 06 C1 00 15 8E C0")


def _config(**overrides):
    base = {
        "reader_host": "192.168.1.200",
        "device_id": "reader-device-001",
        "device_secret": "test-secret",
        "ingest_url": "https://ingest.example.test/ingest/v1/rfid/events",
    }
    base.update(overrides)
    return EdgeConfig(**base)


# --- CRC --------------------------------------------------------------------


def test_crc16_ccitt_matches_vendor_vectors():
    assert srk_idt98.crc16_ccitt(HOST_START_INVENTORY[:-2]) == 0x444C
    assert srk_idt98.crc16_ccitt(TAG_FRAME_1[:-2]) == 0x4D56
    assert srk_idt98.crc16_ccitt(TAG_FRAME_2[:-2]) == 0xB17F
    assert srk_idt98.crc16_ccitt(TIMEOUT_FRAME[:-2]) == 0x8EC0


# --- command builder --------------------------------------------------------


def test_build_start_inventory_matches_vendor_example():
    assert srk_idt98.build_start_inventory(q_value=5, inv_number=188) == HOST_START_INVENTORY


def test_build_start_inventory_round_trips_through_parser():
    cmd = srk_idt98.build_start_inventory(q_value=4, inv_number=0)
    assert cmd[:2] == b"\xAA\xAA"
    assert srk_idt98.crc16_ccitt(cmd[:-2]) == int.from_bytes(cmd[-2:], "big")


def test_build_stop_inventory():
    cmd = srk_idt98.build_stop_inventory()
    assert cmd[4:6] == bytes(srk_idt98.CMD_STOP_MULTI)
    assert srk_idt98.crc16_ccitt(cmd[:-2]) == int.from_bytes(cmd[-2:], "big")


# --- tag parsing ------------------------------------------------------------


def _parse_single(raw: bytes) -> TagRead:
    frames = FrameParser().feed(raw)
    assert len(frames) == 1
    read = srk_idt98.parse_tag_read(frames[0])
    assert read is not None
    return read


def test_parse_tag_frame_epc_rssi_antenna():
    read = _parse_single(TAG_FRAME_1)
    assert read.epc == "E2003009281101461120A520"
    assert read.pc == 0x3000
    assert read.rssi_dbm == -68  # 0xBC signed
    assert read.antenna == 1  # 0x00 -> ANT1
    assert read.stored_crc == 0x2398


def test_parse_tag_frame_second_vector():
    read = _parse_single(TAG_FRAME_2)
    assert read.epc == "11223344556677889900AABB"
    assert read.rssi_dbm == -55  # 0xC9 signed, matches the doc's worked example
    assert read.antenna == 1  # 0x00 -> ANT1


def test_epc_length_derived_from_pc():
    # PC=0x3000 -> (0x3000 >> 11) * 2 = 12 EPC bytes
    read = _parse_single(TAG_FRAME_1)
    assert len(bytes.fromhex(read.epc)) == (read.pc >> 11) * 2


def test_timeout_frame_yields_no_tag_read():
    frames = FrameParser().feed(TIMEOUT_FRAME)
    assert len(frames) == 1
    assert frames[0].status == srk_idt98.STATUS_INVENTORY_TAG_TIMEOUT
    assert srk_idt98.parse_tag_read(frames[0]) is None


def test_inventory_end_frame():
    body = bytes([0xFF, 0x0A, 0xC0, 0x00, 0x00]) + (7).to_bytes(4, "big")
    raw = b"\xAA\xAA" + body
    raw += srk_idt98.crc16_ccitt(raw).to_bytes(2, "big")
    frames = FrameParser().feed(raw)
    assert len(frames) == 1
    end = srk_idt98.parse_inventory_end(frames[0])
    assert end is not None and end.tag_count == 7


# --- stream parser ----------------------------------------------------------


def test_parser_handles_split_chunks():
    parser = FrameParser()
    assert parser.feed(TAG_FRAME_1[:10]) == []
    frames = parser.feed(TAG_FRAME_1[10:])
    assert len(frames) == 1
    assert srk_idt98.parse_tag_read(frames[0]).epc == "E2003009281101461120A520"


def test_parser_handles_multiple_frames_in_one_chunk():
    frames = FrameParser().feed(TAG_FRAME_1 + TAG_FRAME_2 + TIMEOUT_FRAME)
    assert len(frames) == 3
    assert srk_idt98.parse_tag_read(frames[0]).epc == "E2003009281101461120A520"
    assert srk_idt98.parse_tag_read(frames[1]).epc == "11223344556677889900AABB"
    assert srk_idt98.parse_tag_read(frames[2]) is None


def test_parser_resyncs_after_garbage_and_bad_crc():
    corrupt = bytearray(TAG_FRAME_1)
    corrupt[10] ^= 0xFF  # break the CRC
    parser = FrameParser()
    assert parser.feed(b"\x00\xFFgarbage" + bytes(corrupt)) == []
    frames = parser.feed(TAG_FRAME_2)
    assert len(frames) == 1
    assert parser.dropped_bytes > 0


# --- edge dedup -------------------------------------------------------------


def test_edge_dedup_suppresses_repeats_inside_window():
    dedup = EdgeDedup(window_seconds=5.0)
    assert dedup.seen("EPC1", now=100.0) is False
    assert dedup.seen("EPC1", now=102.0) is True
    assert dedup.seen("EPC2", now=102.0) is False
    assert dedup.seen("EPC1", now=106.0) is False  # window expired


# --- canonical event + signing ----------------------------------------------


def test_build_event_canonical_shape():
    read = _parse_single(TAG_FRAME_1)
    event = build_event("reader-device-001", read, direction="in", device_event_id="evt-1")
    assert event["device_event_id"] == "evt-1"
    assert event["uhf_epc"] == "E2003009281101461120A520"
    assert event["antenna"] == 1
    assert event["rssi"] == -68.0
    assert event["direction"] == "in"
    assert "occurred_at" in event
    body = public_event(event)
    assert "_edge" not in body  # debug keys never leave the box


def test_sign_request_matches_ingest_contract():
    config = _config()
    read = _parse_single(TAG_FRAME_1)
    event = build_event(config.device_id, read, None, device_event_id="evt-9")
    signed = sign_request(config, event, nonce="fixed-nonce", timestamp=1770000000)
    assert signed.url == config.ingest_url
    assert signed.headers["X-Device-Id"] == "reader-device-001"
    assert signed.headers["X-Key-Version"] == "1"
    assert signed.headers["X-Timestamp"] == "1770000000"
    assert signed.headers["X-Nonce"] == "fixed-nonce"
    body = json.loads(signed.body)
    assert body["uhf_epc"] == "E2003009281101461120A520"
    # the signature must verify under the server-side verifier
    message = rfid_security.canonical_message(
        method="POST",
        path="/ingest/v1/rfid/events",
        timestamp="1770000000",
        nonce="fixed-nonce",
        body_hash=rfid_security.body_sha256_hex(signed.body),
        device_id="reader-device-001",
        key_version="1",
    )
    assert rfid_security.verify_signature("test-secret", message, signed.headers["X-Signature"])


# --- outbox ------------------------------------------------------------------


def test_outbox_persist_retry_semantics(tmp_path):
    outbox = Outbox(str(tmp_path / "outbox.db"))
    read = _parse_single(TAG_FRAME_1)
    event = build_event("reader-device-001", read, None, device_event_id="evt-42")
    outbox.enqueue(event)
    outbox.enqueue(event)  # duplicate enqueue is a no-op
    assert outbox.pending_count() == 1
    row_id, pending = outbox.oldest_pending()
    assert pending["device_event_id"] == "evt-42"  # same id on retry
    outbox.mark_failed(row_id, "network: timeout")
    assert outbox.pending_count() == 1  # still pending, retried with same id
    outbox.mark_sent(row_id)
    assert outbox.pending_count() == 0
    outbox.close()


def test_outbox_dead_letter_on_permanent_rejection(tmp_path):
    outbox = Outbox(str(tmp_path / "outbox.db"))
    read = _parse_single(TAG_FRAME_1)
    event = build_event("reader-device-001", read, None, device_event_id="evt-43")
    outbox.enqueue(event)
    row_id, _ = outbox.oldest_pending()
    outbox.mark_dead(row_id, "http 401: invalid_signature")
    assert outbox.pending_count() == 0
    outbox.close()
