from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.audit.service import record_audit
from schoolpass.cards.normalize import normalize_hf_uid
from schoolpass.db.mixins import utcnow
from schoolpass.errors import AuthenticationError, NotFoundError, ValidationFailed
from schoolpass.identity.models import ClientDevice
from schoolpass.outbox.service import enqueue_outbox
from schoolpass.rfid.resolution import (
    RESOLUTION_BLOCKED,
    RESOLUTION_RESOLVED,
    RESOLUTION_RETIRED,
    RESOLUTION_UNASSIGNED,
    RESOLUTION_UNKNOWN,
    resolve_card,
)
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.models import (
    ClientEvent,
    TransportAttendant,
    TransportBoardingRecord,
    Trip,
    TripStop,
)
from schoolpass.transport.services import get_effective_transport_assignment

HEADER_CLIENT_DEVICE = "x-client-device-id"

PROCESSING_PROCESSED = "processed"
PROCESSING_REJECTED_PREFIX = "rejected_"


class SyncResultCategory(StrEnum):
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


REJECTION_UNKNOWN_CARD = "unknown_card"
REJECTION_CARD_BLOCKED = "card_blocked"
REJECTION_CARD_RETIRED = "card_retired"
REJECTION_CARD_UNASSIGNED = "card_unassigned"
REJECTION_NO_TRANSPORT_ASSIGNMENT = "no_transport_assignment"
REJECTION_ROUTE_MISMATCH = "route_mismatch"
REJECTION_STOP_MISMATCH = "stop_mismatch"
REJECTION_INVALID_STOP = "invalid_stop"
REJECTION_TRIP = "invalid_trip"
REJECTION_CANCELLED_TRIP = "cancelled_trip"
REJECTION_TRIP_NOT_STARTED = "trip_not_started"
REJECTION_INVALID_EVENT_WINDOW = "invalid_event_window"
REJECTION_INVALID_TRIP_PHASE = "invalid_trip_phase"
REJECTION_BOARDING_REQUIRED = "boarding_required"
REJECTION_ATTENDANT = "unauthorized_attendant"
REJECTION_DEVICE = "invalid_device"
# Legacy alias retained in processing_state only for events stored before 6B.2
REJECTION_TRIP_STOP = REJECTION_INVALID_STOP


@dataclass(frozen=True)
class NfcSyncResult:
    category: SyncResultCategory
    server_event_id: UUID
    client_event_id: UUID
    occurred_at: datetime
    received_at: datetime
    boarding_record_id: UUID | None
    rejection_code: str | None
    device_sequence: int | None


def _require_tenant(ctx: TenantContext) -> UUID:
    if ctx.tenant_id is None:
        raise AuthenticationError("Tenant context is required")
    return ctx.tenant_id


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def _load_client_device(
    session: AsyncSession,
    *,
    client_device_id: UUID,
    user_id: UUID,
) -> ClientDevice:
    device = await session.get(ClientDevice, client_device_id)
    if device is None or device.user_id != user_id:
        raise AuthenticationError("Invalid client device", code=REJECTION_DEVICE)
    if device.status != "active":
        raise AuthenticationError("Client device is not active", code=REJECTION_DEVICE)
    return device


async def _get_attendant_for_user(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
) -> TransportAttendant:
    row = (
        await session.execute(
            select(TransportAttendant).where(
                TransportAttendant.tenant_id == tenant_id,
                TransportAttendant.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None or row.status != "active":
        raise AuthenticationError("Transport attendant profile required", code=REJECTION_ATTENDANT)
    return row


async def _load_trip(session: AsyncSession, tenant_id: UUID, trip_id: UUID) -> Trip | None:
    return (
        await session.execute(select(Trip).where(Trip.id == trip_id, Trip.tenant_id == tenant_id))
    ).scalar_one_or_none()


def _trip_window_rejection(trip: Trip, occurred_at: datetime) -> str | None:
    """Occurrence window semantics: inclusive [started_at, ended_at] when ended_at is set."""
    if trip.status == "cancelled":
        return REJECTION_CANCELLED_TRIP
    if trip.started_at is None:
        return REJECTION_TRIP_NOT_STARTED
    started = _ensure_utc(trip.started_at)
    if occurred_at < started:
        return REJECTION_INVALID_EVENT_WINDOW
    if trip.ended_at is not None and occurred_at > _ensure_utc(trip.ended_at):
        return REJECTION_INVALID_EVENT_WINDOW
    return None


def _trip_phase_rejection(trip: Trip, event_type: str) -> str | None:
    """Current trip status vs event type (after occurrence window checks)."""
    if event_type == "boarding":
        if trip.status == "scheduled":
            return REJECTION_TRIP_NOT_STARTED
        return None
    if event_type == "dropoff":
        if trip.status in {"scheduled", "boarding"}:
            return REJECTION_INVALID_TRIP_PHASE
        return None
    return None


def _map_card_rejection(resolution_status: str) -> str:
    if resolution_status == RESOLUTION_UNKNOWN:
        return REJECTION_UNKNOWN_CARD
    if resolution_status == RESOLUTION_BLOCKED:
        return REJECTION_CARD_BLOCKED
    if resolution_status == RESOLUTION_RETIRED:
        return REJECTION_CARD_RETIRED
    if resolution_status == RESOLUTION_UNASSIGNED:
        return REJECTION_CARD_UNASSIGNED
    return REJECTION_UNKNOWN_CARD


async def _dropoff_sequence_rejection(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    trip_id: UUID,
    student_id: UUID,
    occurred_at: datetime,
) -> str | None:
    prior_boarding = (
        await session.execute(
            select(TransportBoardingRecord.id)
            .where(
                TransportBoardingRecord.tenant_id == tenant_id,
                TransportBoardingRecord.trip_id == trip_id,
                TransportBoardingRecord.student_id == student_id,
                TransportBoardingRecord.event_type == "boarding",
                TransportBoardingRecord.occurred_at <= occurred_at,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if prior_boarding is None:
        return REJECTION_BOARDING_REQUIRED
    return None


async def _fetch_existing_event(
    session: AsyncSession,
    *,
    client_device_id: UUID,
    client_event_id: UUID,
) -> ClientEvent | None:
    return (
        await session.execute(
            select(ClientEvent).where(
                ClientEvent.client_device_id == client_device_id,
                ClientEvent.client_event_id == client_event_id,
            )
        )
    ).scalar_one_or_none()


def _result_from_existing(event: ClientEvent, *, replay: bool) -> NfcSyncResult:
    if event.processing_state == PROCESSING_PROCESSED:
        category = SyncResultCategory.DUPLICATE if replay else SyncResultCategory.PROCESSED
    else:
        category = SyncResultCategory.REJECTED
    return NfcSyncResult(
        category=category,
        server_event_id=event.id,
        client_event_id=event.client_event_id,
        occurred_at=event.occurred_at,
        received_at=event.received_at,
        boarding_record_id=event.transport_boarding_record_id,
        rejection_code=event.rejection_code,
        device_sequence=event.device_sequence,
    )


async def _record_rejection(
    session: AsyncSession,
    ctx: TenantContext,
    event: ClientEvent,
    *,
    rejection_code: str,
    request_id: str | None,
) -> NfcSyncResult:
    if event.rejection_code is not None:
        return _result_from_existing(event, replay=True)
    event.processing_state = f"{PROCESSING_REJECTED_PREFIX}{rejection_code}"
    event.rejection_code = rejection_code
    event.updated_at = utcnow()
    await session.flush()
    await record_audit(
        session,
        ctx,
        action="transport.nfc.rejected",
        resource_type="client_event",
        resource_id=event.id,
        request_id=request_id,
        metadata={"rejection_code": rejection_code, "trip_id": str(event.trip_id)},
    )
    await enqueue_outbox(
        session,
        topic="transport.nfc.rejected",
        idempotency_key=f"transport.nfc.rejected:{event.id}",
        tenant_id=ctx.tenant_id,
        correlation_id=request_id,
        payload={
            "client_event_id": str(event.id),
            "trip_id": str(event.trip_id),
            "rejection_code": rejection_code,
        },
    )
    return NfcSyncResult(
        category=SyncResultCategory.REJECTED,
        server_event_id=event.id,
        client_event_id=event.client_event_id,
        occurred_at=event.occurred_at,
        received_at=event.received_at,
        boarding_record_id=None,
        rejection_code=rejection_code,
        device_sequence=event.device_sequence,
    )


async def _validate_trip_stop(
    session: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    trip_stop_id: UUID | None,
) -> str | None:
    if trip_stop_id is None:
        return None
    stop = (
        await session.execute(
            select(TripStop).where(
                TripStop.id == trip_stop_id,
                TripStop.tenant_id == tenant_id,
                TripStop.trip_id == trip_id,
            )
        )
    ).scalar_one_or_none()
    if stop is None:
        return REJECTION_INVALID_STOP
    return None


async def sync_transport_nfc_event(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    client_device_id: UUID,
    client_event_id: UUID,
    event_type: str,
    card_uid: str,
    occurred_at: datetime,
    trip_id: UUID,
    trip_stop_id: UUID | None = None,
    device_sequence: int | None = None,
    request_id: str | None = None,
) -> NfcSyncResult:
    tenant_id = _require_tenant(ctx)
    if ctx.user_id is None:
        raise AuthenticationError("Authenticated user is required")
    occurred_at = _ensure_utc(occurred_at)
    if event_type not in {"boarding", "dropoff"}:
        raise ValidationFailed("Invalid event type")

    await _load_client_device(session, client_device_id=client_device_id, user_id=ctx.user_id)
    attendant = await _get_attendant_for_user(session, tenant_id, ctx.user_id)

    existing = await _fetch_existing_event(
        session,
        client_device_id=client_device_id,
        client_event_id=client_event_id,
    )
    if existing is not None:
        existing.sync_attempts += 1
        existing.updated_at = utcnow()
        await session.flush()
        return _result_from_existing(existing, replay=True)

    normalized_uid = normalize_hf_uid(card_uid)
    if not normalized_uid:
        raise ValidationFailed("Invalid card UID")

    received_at = utcnow()
    event = ClientEvent(
        tenant_id=tenant_id,
        client_device_id=client_device_id,
        client_event_id=client_event_id,
        actor_user_id=ctx.user_id,
        event_type=event_type,
        card_uid=normalized_uid,
        trip_id=trip_id,
        trip_stop_id=trip_stop_id,
        device_sequence=device_sequence,
        occurred_at=occurred_at,
        received_at=received_at,
        sync_attempts=1,
        processing_state="received",
    )
    session.add(event)
    try:
        await session.flush()
    except IntegrityError as exc:
        orig = str(getattr(exc, "orig", exc))
        if "uq_client_events_device_event" not in orig:
            raise
        raced = await _fetch_existing_event(
            session,
            client_device_id=client_device_id,
            client_event_id=client_event_id,
        )
        if raced is not None:
            raced.sync_attempts += 1
            raced.updated_at = utcnow()
            await session.flush()
            return _result_from_existing(raced, replay=True)
        raise

    trip = await _load_trip(session, tenant_id, trip_id)
    if trip is None:
        return await _record_rejection(
            session, ctx, event, rejection_code=REJECTION_TRIP, request_id=request_id
        )
    if trip.attendant_id != attendant.id:
        return await _record_rejection(
            session, ctx, event, rejection_code=REJECTION_ATTENDANT, request_id=request_id
        )
    stop_reject = await _validate_trip_stop(session, tenant_id, trip.id, trip_stop_id)
    if stop_reject is not None:
        return await _record_rejection(session, ctx, event, rejection_code=stop_reject, request_id=request_id)
    window_reject = _trip_window_rejection(trip, occurred_at)
    if window_reject is not None:
        return await _record_rejection(
            session, ctx, event, rejection_code=window_reject, request_id=request_id
        )
    phase_reject = _trip_phase_rejection(trip, event_type)
    if phase_reject is not None:
        return await _record_rejection(
            session, ctx, event, rejection_code=phase_reject, request_id=request_id
        )

    resolution = await resolve_card(
        session,
        tenant_id,
        hf_uid=normalized_uid,
        uhf_epc=None,
        uhf_tid=None,
        occurred_at=occurred_at,
    )
    if resolution.resolution_status != RESOLUTION_RESOLVED:
        return await _record_rejection(
            session,
            ctx,
            event,
            rejection_code=_map_card_rejection(resolution.resolution_status),
            request_id=request_id,
        )
    assert resolution.student_id is not None
    assert resolution.assignment_id is not None
    assert resolution.physical_card_id is not None

    transport_assignment = await get_effective_transport_assignment(
        session,
        tenant_id=tenant_id,
        student_id=resolution.student_id,
        at_time=occurred_at,
    )
    if transport_assignment is None:
        return await _record_rejection(
            session,
            ctx,
            event,
            rejection_code=REJECTION_NO_TRANSPORT_ASSIGNMENT,
            request_id=request_id,
        )
    if transport_assignment.route_id != trip.route_id:
        return await _record_rejection(
            session, ctx, event, rejection_code=REJECTION_ROUTE_MISMATCH, request_id=request_id
        )
    if trip_stop_id is not None:
        stop = (
            await session.execute(
                select(TripStop).where(
                    TripStop.id == trip_stop_id,
                    TripStop.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if stop is not None and transport_assignment.stop_id != stop.route_stop_id:
            return await _record_rejection(
                session, ctx, event, rejection_code=REJECTION_STOP_MISMATCH, request_id=request_id
            )

    if event_type == "dropoff":
        sequence_reject = await _dropoff_sequence_rejection(
            session,
            tenant_id,
            trip_id=trip.id,
            student_id=resolution.student_id,
            occurred_at=occurred_at,
        )
        if sequence_reject is not None:
            return await _record_rejection(
                session, ctx, event, rejection_code=sequence_reject, request_id=request_id
            )

    boarding = TransportBoardingRecord(
        tenant_id=tenant_id,
        trip_id=trip.id,
        bus_id=trip.bus_id,
        attendant_id=trip.attendant_id,
        student_id=resolution.student_id,
        transport_assignment_id=transport_assignment.id,
        card_assignment_id=resolution.assignment_id,
        physical_card_id=resolution.physical_card_id,
        client_event_id=event.id,
        event_type=event_type,
        occurred_at=occurred_at,
        received_at=received_at,
        trip_stop_id=trip_stop_id,
        source="nfc",
        status="recorded",
        created_at=received_at,
    )
    session.add(boarding)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise NotFoundError() from exc

    event.processing_state = PROCESSING_PROCESSED
    event.transport_boarding_record_id = boarding.id
    event.updated_at = utcnow()
    await session.flush()

    await record_audit(
        session,
        ctx,
        action="transport.boarding.recorded",
        resource_type="transport_boarding_record",
        resource_id=boarding.id,
        request_id=request_id,
        metadata={
            "trip_id": str(trip.id),
            "student_id": str(resolution.student_id),
            "event_type": event_type,
        },
    )
    await enqueue_outbox(
        session,
        topic="transport.boarding.recorded",
        idempotency_key=f"transport.boarding.recorded:{boarding.id}",
        tenant_id=tenant_id,
        correlation_id=request_id,
        payload={
            "boarding_record_id": str(boarding.id),
            "trip_id": str(trip.id),
            "student_id": str(resolution.student_id),
            "event_type": event_type,
            "client_event_id": str(event.id),
        },
    )
    return NfcSyncResult(
        category=SyncResultCategory.PROCESSED,
        server_event_id=event.id,
        client_event_id=client_event_id,
        occurred_at=occurred_at,
        received_at=received_at,
        boarding_record_id=boarding.id,
        rejection_code=None,
        device_sequence=device_sequence,
    )


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
