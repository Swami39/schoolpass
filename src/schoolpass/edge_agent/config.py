"""Edge agent configuration (environment variables)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise ValueError(f"environment variable {name} is required")
    return value or ""


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw in (None, "") else int(raw)


def _get_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return default if raw in (None, "") else float(raw)


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class EdgeConfig:
    # --- reader ---------------------------------------------------------
    reader_host: str
    reader_port: int = 9090
    reader_address: int = 0xFF
    # --- SchoolPass identity --------------------------------------------
    device_id: str = ""
    device_secret: str = ""
    device_key_version: int = 1
    ingest_url: str = ""
    # --- inventory behaviour --------------------------------------------
    start_inventory_on_connect: bool = True
    q_value: int = 4
    inv_number: int = 0  # 0 = inventory forever
    # --- event shaping --------------------------------------------------
    dedup_window_seconds: float = 5.0
    direction: str | None = None  # "in" | "out" | None (server gate config)
    # --- delivery --------------------------------------------------------
    outbox_db: str = "edge_outbox.db"
    post_timeout_seconds: float = 10.0
    retry_interval_seconds: float = 5.0
    reconnect_delay_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "EdgeConfig":
        direction = _get("EDGE_DIRECTION", "").strip().lower() or None
        if direction not in (None, "in", "out"):
            raise ValueError("EDGE_DIRECTION must be 'in', 'out' or empty")
        return cls(
            reader_host=_get("READER_HOST", required=True),
            reader_port=_get_int("READER_PORT", 9090),
            reader_address=int(_get("READER_ADDRESS", "255"), 0),
            device_id=_get("DEVICE_ID", required=True),
            device_secret=_get("DEVICE_SECRET", required=True),
            device_key_version=_get_int("DEVICE_KEY_VERSION", 1),
            ingest_url=_get("INGEST_URL", required=True),
            start_inventory_on_connect=_get_bool("START_INVENTORY_ON_CONNECT", True),
            q_value=_get_int("INVENTORY_Q_VALUE", 4),
            inv_number=_get_int("INVENTORY_NUMBER", 0),
            dedup_window_seconds=_get_float("DEDUP_WINDOW_SECONDS", 5.0),
            direction=direction,
            outbox_db=_get("OUTBOX_DB", "edge_outbox.db"),
            post_timeout_seconds=_get_float("POST_TIMEOUT_SECONDS", 10.0),
            retry_interval_seconds=_get_float("RETRY_INTERVAL_SECONDS", 5.0),
            reconnect_delay_seconds=_get_float("RECONNECT_DELAY_SECONDS", 5.0),
        )
