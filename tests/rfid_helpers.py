from __future__ import annotations

import json
import time
from typing import Any

from schoolpass.rfid.security import INGEST_PATH, body_sha256_hex, canonical_message, compute_signature


def sign_rfid_ingest(
    *,
    secret: str,
    device_id: str,
    key_version: int,
    body: bytes,
    nonce: str | None = None,
    timestamp: int | None = None,
    method: str = "POST",
    path: str = INGEST_PATH,
) -> dict[str, str]:
    ts = str(timestamp if timestamp is not None else int(time.time()))
    nonce_val = nonce or f"nonce-{time.time_ns()}"
    body_hash = body_sha256_hex(body)
    message = canonical_message(
        method=method,
        path=path,
        timestamp=ts,
        nonce=nonce_val,
        body_hash=body_hash,
        device_id=device_id,
        key_version=str(key_version),
    )
    signature = compute_signature(secret, message)
    return {
        "X-Device-Id": device_id,
        "X-Key-Version": str(key_version),
        "X-Timestamp": ts,
        "X-Nonce": nonce_val,
        "X-Signature": signature,
    }


def event_body(**fields: Any) -> bytes:
    return json.dumps(fields, default=str).encode("utf-8")
