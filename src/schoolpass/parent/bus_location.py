from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.adapters.redis import Cache
from schoolpass.errors import NotFoundError
from schoolpass.identity.models import Tenant
from schoolpass.people.models import Guardian, StudentGuardian
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.gps_redis import get_trip_last_location, trip_last_key
from schoolpass.transport.models import Trip
from schoolpass.transport.services import get_effective_transport_assignment


class ParentBusLocationStatus(StrEnum):
    AVAILABLE = "available"
    NO_ASSIGNMENT = "no_assignment"
    NO_ACTIVE_TRIP = "no_active_trip"
    LOCATION_UNAVAILABLE = "location_unavailable"
    CACHE_UNAVAILABLE = "cache_unavailable"


@dataclass(frozen=True)
class ParentBusLocationResult:
    student_id: UUID
    status: ParentBusLocationStatus
    bus_id: UUID | None = None
    trip_id: UUID | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    occurred_at: datetime | None = None
    received_at: datetime | None = None
    accuracy_meters: Decimal | None = None


async def _tenant_service_date(session: AsyncSession, tenant_id: UUID) -> date:
    tenant = await session.get(Tenant, tenant_id)
    tz_name = tenant.timezone if tenant is not None else "UTC"
    return datetime.now(ZoneInfo(tz_name)).date()


async def _load_guardian_for_user(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
) -> Guardian:
    row = (
        await session.execute(
            select(Guardian).where(
                Guardian.tenant_id == tenant_id,
                Guardian.user_id == user_id,
                Guardian.status == "active",
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError()
    return row


async def _assert_guardian_linked_to_student(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    guardian_id: UUID,
    student_id: UUID,
) -> None:
    link = (
        await session.execute(
            select(StudentGuardian.id).where(
                StudentGuardian.tenant_id == tenant_id,
                StudentGuardian.guardian_id == guardian_id,
                StudentGuardian.student_id == student_id,
                StudentGuardian.status == "active",
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise NotFoundError()


async def _find_active_trip_for_assignment(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    route_id: UUID,
    service_date: date,
) -> Trip | None:
    return (
        await session.execute(
            select(Trip)
            .where(
                Trip.tenant_id == tenant_id,
                Trip.route_id == route_id,
                Trip.service_date == service_date,
                Trip.status == "in_progress",
            )
            .order_by(Trip.started_at.desc().nulls_last(), Trip.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def get_parent_child_bus_location(
    session: AsyncSession,
    ctx: TenantContext,
    redis: Cache,
    *,
    student_id: UUID,
) -> ParentBusLocationResult:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()

    tenant_id = ctx.tenant_id
    guardian = await _load_guardian_for_user(session, tenant_id=tenant_id, user_id=ctx.user_id)
    await _assert_guardian_linked_to_student(
        session,
        tenant_id=tenant_id,
        guardian_id=guardian.id,
        student_id=student_id,
    )

    service_date = await _tenant_service_date(session, tenant_id)
    assignment = await get_effective_transport_assignment(
        session,
        tenant_id=tenant_id,
        student_id=student_id,
        at_time=service_date,
    )
    if assignment is None:
        return ParentBusLocationResult(
            student_id=student_id,
            status=ParentBusLocationStatus.NO_ASSIGNMENT,
        )

    trip = await _find_active_trip_for_assignment(
        session,
        tenant_id=tenant_id,
        route_id=assignment.route_id,
        service_date=service_date,
    )
    if trip is None:
        return ParentBusLocationResult(
            student_id=student_id,
            status=ParentBusLocationStatus.NO_ACTIVE_TRIP,
        )

    try:
        cached = await get_trip_last_location(redis, trip.id)
    except Exception:
        return ParentBusLocationResult(
            student_id=student_id,
            status=ParentBusLocationStatus.CACHE_UNAVAILABLE,
            bus_id=trip.bus_id,
            trip_id=trip.id,
        )

    if cached is None:
        return ParentBusLocationResult(
            student_id=student_id,
            status=ParentBusLocationStatus.LOCATION_UNAVAILABLE,
            bus_id=trip.bus_id,
            trip_id=trip.id,
        )

    if cached.trip_id != trip.id or cached.bus_id != trip.bus_id:
        return ParentBusLocationResult(
            student_id=student_id,
            status=ParentBusLocationStatus.LOCATION_UNAVAILABLE,
            bus_id=trip.bus_id,
            trip_id=trip.id,
        )

    return ParentBusLocationResult(
        student_id=student_id,
        status=ParentBusLocationStatus.AVAILABLE,
        bus_id=trip.bus_id,
        trip_id=trip.id,
        latitude=cached.latitude,
        longitude=cached.longitude,
        occurred_at=cached.occurred_at,
        received_at=cached.received_at,
        accuracy_meters=cached.accuracy_meters,
    )


def authorized_trip_redis_key(trip_id: UUID) -> str:
    """Expose key construction for tests (server-side only)."""
    return trip_last_key(trip_id)
