"""SRK Innovations / IDT98-series UHF reader wire protocol.

Covers the SRK-6GWL (and the wider IDT98 / IDT95 family, firmware
``20.0X.03.70``) speaking its native binary protocol over TCP or RS-232,
as documented in "IoT UHF Reader & Module API Communication Protocol
V3.0.0" and the "Reader 86L_98L configuration manual".

Frame layout (response frame shown; command frames omit STATUS)::

    AA AA | RA | LEN | CMDH CMDL | STATUS | DATA(0..128) | CRCH CRCL

- ``LEN`` counts every byte from the LEN field itself through the CRC.
- CRC is CRC-CCITT (poly 0x1021, init 0xFFFF) over everything except the
  CRC bytes.
- Multi-tag inventory (0xC1) response DATA per tag::

    RSSI(1, signed dBm) | PC(2) | EPC((PC>>11)*2 bytes) | StoredCRC(2) | ANT(1)

This module only parses bytes and builds command bytes. Turning reads
into signed canonical ingest events is the edge agent's job
(``schoolpass.edge_agent``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

FRAME_HEADER = b"\xAA\xAA"
BROADCAST_ADDRESS = 0xFF

# --- commands ---------------------------------------------------------------
CMD_STOP_MULTI = (0xC0, 0x00)
CMD_MULTI_ID = (0xC1, 0x00)  # algorithm 0
CMD_MULTI_ID_ALG1 = (0xC1, 0x01)  # algorithm 1
CMD_MULTI_ID_ALG2 = (0xC1, 0x02)  # algorithm 2

# --- status codes -----------------------------------------------------------
STATUS_OK = 0x00
STATUS_INVENTORY_TAG_TIMEOUT = 0x15

# --- antenna ----------------------------------------------------------------
# ANT byte 0x00 -> ANT1, 0x01 -> ANT2, ...


def crc16_ccitt(data: bytes, init: int = 0xFFFF) -> int:
    """CRC-CCITT (poly 0x1021, init 0xFFFF) per the vendor protocol doc."""
    crc = init & 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def build_command(cmdh: int, cmdl: int, params: bytes = b"", address: int = BROADCAST_ADDRESS) -> bytes:
    """Build a host->reader command frame."""
    if not 0 <= address <= 0xFF:
        raise ValueError("address out of range")
    if len(params) > 32:
        raise ValueError("parameter domain is at most 32 bytes")
    body = bytes([cmdh, cmdl]) + bytes(params)
    length = 1 + len(body) + 2  # LEN field itself + body + CRC
    frame = FRAME_HEADER + bytes([address, length]) + body
    return frame + crc16_ccitt(frame).to_bytes(2, "big")


def build_start_inventory(
    q_value: int = 4, inv_number: int = 0, algorithm: int = 0, address: int = BROADCAST_ADDRESS
) -> bytes:
    """Build 0xC1 start multi-tag inventory.

    q_value: Q value; the reader scans a 2**Q - 1 tag population per round.
    inv_number: 0 = inventory forever; otherwise stop after N rounds.
    algorithm: 0, 1 or 2 -> sub-command 0x00/0x01/0x02.
    """
    if algorithm not in (0, 1, 2):
        raise ValueError("algorithm must be 0, 1 or 2")
    if not 0 <= q_value <= 15:
        raise ValueError("q_value out of range")
    if not 0 <= inv_number <= 0xFFFF:
        raise ValueError("inv_number out of range")
    params = bytes([q_value]) + inv_number.to_bytes(2, "big")
    return build_command(0xC1, algorithm, params, address)


def build_stop_inventory(address: int = BROADCAST_ADDRESS) -> bytes:
    """Build 0xC0 stop multi-tag inventory."""
    return build_command(*CMD_STOP_MULTI, b"", address)


@dataclass(frozen=True)
class TagRead:
    """One decoded tag sighting from a 0xC1 inventory response."""

    epc: str  # uppercase hex, no spaces
    pc: int
    rssi_dbm: int  # signed dBm
    antenna: int  # 1-based antenna number (ANT1 == 1)
    stored_crc: int
    stored_crc_ok: bool
    address: int = BROADCAST_ADDRESS


@dataclass(frozen=True)
class InventoryEnd:
    """Reader finished a bounded inventory run (0xC0 response)."""

    tag_count: int
    address: int = BROADCAST_ADDRESS


@dataclass
class Frame:
    """A validated response frame (CRC already checked)."""

    address: int
    cmdh: int
    cmdl: int
    status: int
    data: bytes
    raw: bytes = field(repr=False)


class FrameParser:
    """Incremental parser for the reader byte stream.

    Feed arbitrary chunks from the TCP/serial socket; ``feed`` returns a
    list of validated :class:`Frame` objects. CRC failures cause a
    one-byte resync so a corrupt frame cannot wedge the stream.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self.dropped_bytes = 0

    def feed(self, chunk: bytes) -> list[Frame]:
        self._buf += chunk
        frames: list[Frame] = []
        buf = self._buf
        while True:
            start = buf.find(FRAME_HEADER)
            if start < 0:
                # keep a trailing 0xAA in case the header is split across reads
                if buf.endswith(b"\xAA"):
                    del buf[:-1]
                else:
                    buf.clear()
                break
            if start > 0:
                self.dropped_bytes += start
                del buf[:start]
            if len(buf) < 4:  # need AA AA RA LEN
                break
            length = buf[3]
            if length < 6:  # LEN + CMD(2) + STATUS(1) + CRC(2) minimum
                self.dropped_bytes += 2
                del buf[:2]
                continue
            total = 3 + length
            if len(buf) < total:
                break
            raw = bytes(buf[:total])
            del buf[:total]
            if crc16_ccitt(raw[:-2]) != int.from_bytes(raw[-2:], "big"):
                self.dropped_bytes += total
                continue
            frames.append(
                Frame(
                    address=raw[2],
                    cmdh=raw[4],
                    cmdl=raw[5],
                    status=raw[6],
                    data=raw[7:-2],
                    raw=raw,
                )
            )
        return frames


def parse_tag_read(frame: Frame) -> TagRead | None:
    """Decode a 0xC1 tag-report frame into a :class:`TagRead`.

    Returns ``None`` for non-tag frames (timeouts, inventory-end, ...).
    Raises ``ValueError`` if a tag frame is structurally invalid.
    """
    if (frame.cmdh, frame.cmdl) not in ((0xC1, 0x00), (0xC1, 0x01), (0xC1, 0x02)):
        return None
    if frame.status != STATUS_OK:
        return None
    data = frame.data
    if len(data) < 6:
        raise ValueError("tag data too short")
    rssi = int.from_bytes(data[0:1], "big", signed=True)
    pc = int.from_bytes(data[1:3], "big")
    epc_len = (pc >> 11) * 2
    if epc_len == 0 or len(data) != 6 + epc_len:
        raise ValueError(f"tag data length {len(data)} inconsistent with PC {pc:#06x}")
    epc = data[3 : 3 + epc_len]
    stored_crc = int.from_bytes(data[3 + epc_len : 5 + epc_len], "big")
    antenna = data[5 + epc_len] + 1  # 0x00 -> ANT1
    computed = crc16_ccitt(data[1 : 3 + epc_len])
    return TagRead(
        epc=epc.hex().upper(),
        pc=pc,
        rssi_dbm=rssi,
        antenna=antenna,
        stored_crc=stored_crc,
        stored_crc_ok=(computed == stored_crc),
        address=frame.address,
    )


def parse_inventory_end(frame: Frame) -> InventoryEnd | None:
    """Decode a 0xC0 inventory-end frame (4-byte tag counter)."""
    if (frame.cmdh, frame.cmdl) != CMD_STOP_MULTI:
        return None
    if frame.status != STATUS_OK or len(frame.data) != 4:
        return None
    return InventoryEnd(tag_count=int.from_bytes(frame.data, "big"), address=frame.address)
