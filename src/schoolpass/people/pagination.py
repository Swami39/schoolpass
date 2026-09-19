from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any
from uuid import UUID


def encode_cursor(*, created_at: datetime, row_id: UUID) -> str:
    payload = {"created_at": created_at.isoformat(), "id": str(row_id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str | None) -> tuple[datetime, UUID] | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        data: dict[str, Any] = json.loads(raw)
        return datetime.fromisoformat(data["created_at"]), UUID(data["id"])
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid cursor") from exc
