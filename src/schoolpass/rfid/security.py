from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime

INGEST_PATH = "/ingest/v1/rfid/events"


def generate_device_secret() -> str:
    return secrets.token_urlsafe(32)


def body_sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_message(
    *,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body_hash: str,
    device_id: str,
    key_version: str,
) -> str:
    return "\n".join([method.upper(), path, timestamp, nonce, body_hash, device_id, key_version])


def compute_signature(secret: str, message: str) -> str:
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(secret: str, message: str, signature: str) -> bool:
    expected = compute_signature(secret, message)
    return hmac.compare_digest(expected, signature.lower())


def parse_request_timestamp(raw: str, *, max_skew_seconds: int) -> datetime:
    try:
        ts = int(raw)
    except ValueError as exc:
        raise ValueError("invalid_timestamp") from exc
    occurred = datetime.fromtimestamp(ts, tz=UTC)
    now = datetime.now(tz=UTC)
    delta = abs((now - occurred).total_seconds())
    if delta > max_skew_seconds:
        raise ValueError("expired_timestamp")
    return occurred
