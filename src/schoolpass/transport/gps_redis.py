from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from schoolpass.adapters.redis import Cache
from schoolpass.observability.logging import get_logger

log = get_logger("schoolpass.transport.gps_redis")

TRIP_LAST_KEY_PREFIX = "trip:"
TRIP_LAST_KEY_SUFFIX = ":last"


@dataclass(frozen=True)
class TripLastLocation:
    trip_id: UUID
    bus_id: UUID
    latitude: Decimal
    longitude: Decimal
    occurred_at: datetime
    accuracy_meters: Decimal | None
    received_at: datetime

    def to_json(self) -> str:
        payload = {
            "trip_id": str(self.trip_id),
            "bus_id": str(self.bus_id),
            "latitude": str(self.latitude),
            "longitude": str(self.longitude),
            "occurred_at": self.occurred_at.isoformat(),
            "received_at": self.received_at.isoformat(),
        }
        if self.accuracy_meters is not None:
            payload["accuracy_meters"] = str(self.accuracy_meters)
        return json.dumps(payload)

    @classmethod
    def from_json(cls, raw: str) -> TripLastLocation:
        data = json.loads(raw)
        return cls(
            trip_id=UUID(data["trip_id"]),
            bus_id=UUID(data["bus_id"]),
            latitude=Decimal(data["latitude"]),
            longitude=Decimal(data["longitude"]),
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
            accuracy_meters=Decimal(data["accuracy_meters"]) if data.get("accuracy_meters") else None,
            received_at=datetime.fromisoformat(data["received_at"]),
        )


def trip_last_key(trip_id: UUID) -> str:
    return f"{TRIP_LAST_KEY_PREFIX}{trip_id}{TRIP_LAST_KEY_SUFFIX}"


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def update_trip_last_location_if_newer(redis: Cache, sample: TripLastLocation) -> bool:
    """Update Redis latest location only when sample occurred_at is newer than cached."""
    key = trip_last_key(sample.trip_id)
    existing_raw = await redis.get(key)
    if existing_raw is not None:
        existing = TripLastLocation.from_json(existing_raw.decode("utf-8"))
        if _ensure_utc(existing.occurred_at) >= _ensure_utc(sample.occurred_at):
            return False
    await redis.set(key, sample.to_json(), ex=86400)
    return True


async def get_trip_last_location(redis: Cache, trip_id: UUID) -> TripLastLocation | None:
    raw = await redis.get(trip_last_key(trip_id))
    if raw is None:
        return None
    return TripLastLocation.from_json(raw.decode("utf-8"))


async def try_update_trip_last_location(redis: Cache, sample: TripLastLocation) -> None:
    """Best-effort cache update; logs and swallows Redis failures."""
    try:
        await update_trip_last_location_if_newer(redis, sample)
    except Exception:
        log.warning("gps_redis_update_failed", trip_id=str(sample.trip_id))
