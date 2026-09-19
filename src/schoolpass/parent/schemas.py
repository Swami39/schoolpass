"""Parent-facing transport read APIs (Phase 6D.1)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from schoolpass.parent.bus_location import ParentBusLocationResult, ParentBusLocationStatus


class ParentBusLocationResponse(BaseModel):
    student_id: UUID
    status: str
    bus_id: UUID | None = None
    trip_id: UUID | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    occurred_at: str | None = None
    received_at: str | None = None
    accuracy_meters: Decimal | None = None

    @classmethod
    def from_result(cls, result: ParentBusLocationResult) -> ParentBusLocationResponse:
        return cls(
            student_id=result.student_id,
            status=result.status.value,
            bus_id=result.bus_id,
            trip_id=result.trip_id,
            latitude=result.latitude if result.status == ParentBusLocationStatus.AVAILABLE else None,
            longitude=result.longitude if result.status == ParentBusLocationStatus.AVAILABLE else None,
            occurred_at=result.occurred_at.isoformat() if result.occurred_at else None,
            received_at=result.received_at.isoformat() if result.received_at else None,
            accuracy_meters=result.accuracy_meters if result.status == ParentBusLocationStatus.AVAILABLE else None,
        )
