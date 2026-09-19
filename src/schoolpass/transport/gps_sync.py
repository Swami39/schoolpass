from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.db.mixins import utcnow
from schoolpass.errors import AuthenticationError, ValidationFailed
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.models import LocationSample, Trip
from schoolpass.transport.nfc_sync import (
    REJECTION_ATTENDANT,
    REJECTION_CANCELLED_TRIP,
    REJECTION_DEVICE,
    REJECTION_INVALID_TRIP_PHASE,
    REJECTION_TRIP,
    _ensure_utc,
    _get_attendant_for_user,
    _load_client_device,
    _load_trip,
    _trip_window_rejection,
)

HEADER_CLIENT_DEVICE = "x-client-device-id"
MAX_GPS_BATCH_SIZE = 50

PROCESSING_RECORDED = "recorded"
PROCESSING_REJECTED = "rejected"

REJECTION_INVALID_LATITUDE = "invalid_latitude"
REJECTION_INVALID_LONGITUDE = "invalid_longitude"
REJECTION_INVALID_ACCURACY = "invalid_accuracy"
REJECTION_INVALID_SPEED = "invalid_speed"
REJECTION_INVALID_HEADING = "invalid_heading"
REJECTION_BUS_MISMATCH = "bus_mismatch"


class GpsSyncResultCategory(StrEnum):
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


@dataclass(frozen=True)
class GpsSampleInput:
    client_sample_id: UUID
    trip_id: UUID
    latitude: Decimal
    longitude: Decimal
    occurred_at: datetime
    bus_id: UUID | None = None
    accuracy_meters: Decimal | None = None
    altitude_meters: Decimal | None = None
    speed_mps: Decimal | None = None
    heading_degrees: Decimal | None = None
    device_sequence: int | None = None
    source: str = "phone_gnss"


@dataclass(frozen=True)
class GpsSampleSyncResult:
    category: GpsSyncResultCategory
    client_sample_id: UUID
    server_sample_id: UUID
    occurred_at: datetime
    received_at: datetime
    rejection_code: str | None
    device_sequence: int | None
    trip_id: UUID | None = None
    bus_id: UUID | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    accuracy_meters: Decimal | None = None
    cache_latest: bool = False


def _require_tenant(ctx: TenantContext) -> UUID:
    if ctx.tenant_id is None:
        raise AuthenticationError("Tenant context is required")
    return ctx.tenant_id


def _validate_coordinates(sample: GpsSampleInput) -> str | None:
    if sample.latitude < Decimal("-90") or sample.latitude > Decimal("90"):
        return REJECTION_INVALID_LATITUDE
    if sample.longitude < Decimal("-180") or sample.longitude > Decimal("180"):
        return REJECTION_INVALID_LONGITUDE
    if sample.accuracy_meters is not None and sample.accuracy_meters < 0:
        return REJECTION_INVALID_ACCURACY
    if sample.speed_mps is not None and sample.speed_mps < 0:
        return REJECTION_INVALID_SPEED
    if sample.heading_degrees is not None and (
        sample.heading_degrees < 0 or sample.heading_degrees >= Decimal("360")
    ):
        return REJECTION_INVALID_HEADING
    if sample.source not in {"phone_gnss", "hardware_tracker"}:
        raise ValidationFailed("Invalid GPS source")
    return None


def _gps_phase_rejection(trip: Trip, occurred_at: datetime) -> str | None:
    if trip.status == "cancelled":
        return REJECTION_CANCELLED_TRIP
    window = _trip_window_rejection(trip, occurred_at)
    if window is not None:
        return window
    if trip.status == "in_progress":
        return None
    if trip.status == "completed":
        return None
    if trip.status in {"scheduled", "boarding"}:
        return REJECTION_INVALID_TRIP_PHASE
    return REJECTION_INVALID_TRIP_PHASE


async def _fetch_existing_sample(
    session: AsyncSession,
    *,
    client_device_id: UUID,
    client_sample_id: UUID,
) -> LocationSample | None:
    return (
        await session.execute(
            select(LocationSample).where(
                LocationSample.client_device_id == client_device_id,
                LocationSample.client_sample_id == client_sample_id,
            )
        )
    ).scalar_one_or_none()


def _result_from_existing(sample: LocationSample, *, replay: bool) -> GpsSampleSyncResult:
    if sample.processing_state == PROCESSING_RECORDED:
        category = GpsSyncResultCategory.DUPLICATE if replay else GpsSyncResultCategory.PROCESSED
    else:
        category = GpsSyncResultCategory.REJECTED
        if replay and sample.rejection_code is not None:
            category = GpsSyncResultCategory.REJECTED
    return GpsSampleSyncResult(
        category=category,
        client_sample_id=sample.client_sample_id,
        server_sample_id=sample.id,
        occurred_at=sample.occurred_at,
        received_at=sample.received_at,
        rejection_code=sample.rejection_code,
        device_sequence=sample.device_sequence,
        trip_id=sample.trip_id,
        bus_id=sample.bus_id,
        latitude=sample.latitude,
        longitude=sample.longitude,
        accuracy_meters=sample.accuracy_meters,
    )


async def sync_transport_gps_sample(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    client_device_id: UUID,
    sample: GpsSampleInput,
) -> GpsSampleSyncResult:
    tenant_id = _require_tenant(ctx)
    if ctx.user_id is None:
        raise AuthenticationError("Authenticated user is required")

    occurred_at = _ensure_utc(sample.occurred_at)

    await _load_client_device(session, client_device_id=client_device_id, user_id=ctx.user_id)
    attendant = await _get_attendant_for_user(session, tenant_id, ctx.user_id)

    existing = await _fetch_existing_sample(
        session,
        client_device_id=client_device_id,
        client_sample_id=sample.client_sample_id,
    )
    if existing is not None:
        return _result_from_existing(existing, replay=True)

    coord_error = _validate_coordinates(sample)
    if coord_error is not None:
        return await _persist_rejection(
            session,
            tenant_id=tenant_id,
            client_device_id=client_device_id,
            sample=sample,
            occurred_at=occurred_at,
            rejection_code=coord_error,
            attendant_id=attendant.id,
            bus_id=sample.bus_id or UUID(int=0),
        )

    trip = await _load_trip(session, tenant_id, sample.trip_id)
    if trip is None:
        return await _persist_rejection(
            session,
            tenant_id=tenant_id,
            client_device_id=client_device_id,
            sample=sample,
            occurred_at=occurred_at,
            rejection_code=REJECTION_TRIP,
            attendant_id=attendant.id,
            bus_id=sample.bus_id or UUID(int=0),
        )

    if trip.attendant_id != attendant.id:
        return await _persist_rejection(
            session,
            tenant_id=tenant_id,
            client_device_id=client_device_id,
            sample=sample,
            occurred_at=occurred_at,
            rejection_code=REJECTION_ATTENDANT,
            attendant_id=attendant.id,
            bus_id=trip.bus_id,
        )

    if sample.bus_id is not None and sample.bus_id != trip.bus_id:
        return await _persist_rejection(
            session,
            tenant_id=tenant_id,
            client_device_id=client_device_id,
            sample=sample,
            occurred_at=occurred_at,
            rejection_code=REJECTION_BUS_MISMATCH,
            attendant_id=attendant.id,
            bus_id=trip.bus_id,
        )

    phase_error = _gps_phase_rejection(trip, occurred_at)
    if phase_error is not None:
        return await _persist_rejection(
            session,
            tenant_id=tenant_id,
            client_device_id=client_device_id,
            sample=sample,
            occurred_at=occurred_at,
            rejection_code=phase_error,
            attendant_id=attendant.id,
            bus_id=trip.bus_id,
        )

    received_at = utcnow()
    row = LocationSample(
        id=uuid4(),
        tenant_id=tenant_id,
        client_device_id=client_device_id,
        client_sample_id=sample.client_sample_id,
        trip_id=trip.id,
        bus_id=trip.bus_id,
        attendant_id=attendant.id,
        latitude=sample.latitude,
        longitude=sample.longitude,
        accuracy_meters=sample.accuracy_meters,
        altitude_meters=sample.altitude_meters,
        speed_mps=sample.speed_mps,
        heading_degrees=sample.heading_degrees,
        occurred_at=occurred_at,
        received_at=received_at,
        device_sequence=sample.device_sequence,
        source=sample.source,
        processing_state=PROCESSING_RECORDED,
        rejection_code=None,
        created_at=received_at,
    )
    session.add(row)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        existing = await _fetch_existing_sample(
            session,
            client_device_id=client_device_id,
            client_sample_id=sample.client_sample_id,
        )
        if existing is None:
            raise
        return _result_from_existing(existing, replay=True)

    return GpsSampleSyncResult(
        category=GpsSyncResultCategory.PROCESSED,
        client_sample_id=sample.client_sample_id,
        server_sample_id=row.id,
        occurred_at=occurred_at,
        received_at=received_at,
        rejection_code=None,
        device_sequence=sample.device_sequence,
        trip_id=row.trip_id,
        bus_id=row.bus_id,
        latitude=row.latitude,
        longitude=row.longitude,
        accuracy_meters=row.accuracy_meters,
        cache_latest=trip.status == "in_progress",
    )


async def _persist_rejection(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    client_device_id: UUID,
    sample: GpsSampleInput,
    occurred_at: datetime,
    rejection_code: str,
    attendant_id: UUID,
    bus_id: UUID,
) -> GpsSampleSyncResult:
    existing = await _fetch_existing_sample(
        session,
        client_device_id=client_device_id,
        client_sample_id=sample.client_sample_id,
    )
    if existing is not None:
        return _result_from_existing(existing, replay=True)

    received_at = utcnow()
    trip = await _load_trip(session, tenant_id, sample.trip_id)
    resolved_bus = trip.bus_id if trip is not None else bus_id
    resolved_attendant = attendant_id
    row = LocationSample(
        id=uuid4(),
        tenant_id=tenant_id,
        client_device_id=client_device_id,
        client_sample_id=sample.client_sample_id,
        trip_id=sample.trip_id,
        bus_id=resolved_bus,
        attendant_id=resolved_attendant,
        latitude=sample.latitude,
        longitude=sample.longitude,
        accuracy_meters=sample.accuracy_meters,
        altitude_meters=sample.altitude_meters,
        speed_mps=sample.speed_mps,
        heading_degrees=sample.heading_degrees,
        occurred_at=occurred_at,
        received_at=received_at,
        device_sequence=sample.device_sequence,
        source=sample.source,
        processing_state=PROCESSING_REJECTED,
        rejection_code=rejection_code,
        created_at=received_at,
    )
    session.add(row)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        existing = await _fetch_existing_sample(
            session,
            client_device_id=client_device_id,
            client_sample_id=sample.client_sample_id,
        )
        if existing is None:
            raise
        return _result_from_existing(existing, replay=True)

    return GpsSampleSyncResult(
        category=GpsSyncResultCategory.REJECTED,
        client_sample_id=sample.client_sample_id,
        server_sample_id=row.id,
        occurred_at=occurred_at,
        received_at=received_at,
        rejection_code=rejection_code,
        device_sequence=sample.device_sequence,
    )


async def sync_transport_gps_batch(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    client_device_id: UUID,
    samples: list[GpsSampleInput],
) -> list[GpsSampleSyncResult]:
    if len(samples) > MAX_GPS_BATCH_SIZE:
        raise ValidationFailed(f"Batch size exceeds maximum of {MAX_GPS_BATCH_SIZE}")
    if not samples:
        raise ValidationFailed("At least one sample is required")
    results: list[GpsSampleSyncResult] = []
    for item in samples:
        results.append(
            await sync_transport_gps_sample(
                session,
                ctx,
                client_device_id=client_device_id,
                sample=item,
            )
        )
    return results


async def get_client_device_for_request(
    session: AsyncSession,
    *,
    header_value: str | None,
    user_id: UUID,
) -> UUID:
    if not header_value or not header_value.strip():
        raise AuthenticationError("Client device header is required", code=REJECTION_DEVICE)
    try:
        device_id = UUID(header_value.strip())
    except ValueError as exc:
        raise AuthenticationError("Invalid client device header", code=REJECTION_DEVICE) from exc
    await _load_client_device(session, client_device_id=device_id, user_id=user_id)
    return device_id
