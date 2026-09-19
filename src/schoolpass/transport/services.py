from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.audit.service import record_audit
from schoolpass.db.mixins import utcnow
from schoolpass.errors import ConflictError, NotFoundError, ValidationFailed
from schoolpass.identity.models import StaffProfile
from schoolpass.outbox.service import enqueue_outbox
from schoolpass.people.models import Student
from schoolpass.people.pagination import decode_cursor, encode_cursor
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.lifecycle import (
    ACTIVE_TRIP_STATUSES,
    ATTENDANT_OPERATIONAL_STATUS,
    BUS_OPERATIONAL_STATUS,
    ROUTE_OPERATIONAL_STATUS,
    TERMINAL_ASSIGNMENT_STATUSES,
    VALID_ROUTE_DIRECTIONS,
    VALID_SHIFTS,
    assert_bus_status_transition,
    assert_route_status_transition,
    assert_trip_status_transition,
)
from schoolpass.transport.models import (
    Bus,
    Route,
    RouteStop,
    TransportAssignment,
    TransportAttendant,
    Trip,
    TripStop,
)

MAX_PAGE_SIZE = 200


async def _audit(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    action: str,
    resource_type: str,
    resource_id: UUID,
    request_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await record_audit(
        session,
        ctx,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        metadata=metadata or {},
    )


async def _outbox(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    topic: str,
    idempotency_key: str,
    payload: dict[str, Any],
    request_id: str | None,
) -> None:
    await enqueue_outbox(
        session,
        topic=topic,
        idempotency_key=idempotency_key,
        tenant_id=ctx.tenant_id,
        correlation_id=request_id,
        payload=payload,
    )


def _require_tenant(ctx: TenantContext) -> UUID:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    return ctx.tenant_id


def _validation_from_value_error(exc: ValueError) -> ValidationFailed:
    return ValidationFailed(str(exc))


def _validate_capacity(capacity: int) -> None:
    if capacity <= 0:
        raise ValidationFailed("Capacity must be positive")


def _validate_coordinates(latitude: Decimal, longitude: Decimal) -> None:
    if latitude < Decimal("-90") or latitude > Decimal("90"):
        raise ValidationFailed("Invalid latitude")
    if longitude < Decimal("-180") or longitude > Decimal("180"):
        raise ValidationFailed("Invalid longitude")


def _validate_geofence(radius_meters: int) -> None:
    if radius_meters <= 0:
        raise ValidationFailed("Geofence radius must be positive")


def _validate_assignment_dates(effective_from: date, effective_to: date | None) -> None:
    if effective_to is not None and effective_to < effective_from:
        raise ValidationFailed("effective_to must be on or after effective_from")


def _as_effective_date(at_time: datetime | date) -> date:
    return at_time.date() if isinstance(at_time, datetime) else at_time


def _date_ranges_overlap(
    a_from: date,
    a_to: date | None,
    b_from: date,
    b_to: date | None,
) -> bool:
    a_end = a_to or date.max
    b_end = b_to or date.max
    return a_from <= b_end and b_from <= a_end


async def get_bus(session: AsyncSession, ctx: TenantContext, bus_id: UUID) -> Bus:
    row = await session.get(Bus, bus_id)
    if row is None:
        raise NotFoundError()
    return row


async def create_bus(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    registration_number: str,
    display_name: str,
    capacity: int,
    fleet_number: str | None = None,
    request_id: str | None = None,
) -> Bus:
    tenant_id = _require_tenant(ctx)
    registration_number = registration_number.strip()
    if not registration_number:
        raise ValidationFailed("Registration number is required")
    if not display_name.strip():
        raise ValidationFailed("Display name is required")
    _validate_capacity(capacity)
    row = Bus(
        tenant_id=tenant_id,
        registration_number=registration_number,
        fleet_number=fleet_number.strip() if fleet_number else None,
        display_name=display_name.strip(),
        capacity=capacity,
        status="active",
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Bus registration or fleet number already exists") from exc
    await _audit(
        session,
        ctx,
        action="bus.created",
        resource_type="bus",
        resource_id=row.id,
        request_id=request_id,
        metadata={"registration_number": registration_number},
    )
    await _outbox(
        session,
        ctx,
        topic="bus.created",
        idempotency_key=f"bus.created:{row.id}",
        payload={"bus_id": str(row.id)},
        request_id=request_id,
    )
    return row


async def update_bus(
    session: AsyncSession,
    ctx: TenantContext,
    bus_id: UUID,
    *,
    registration_number: str | None = None,
    fleet_number: str | None = None,
    display_name: str | None = None,
    capacity: int | None = None,
    request_id: str | None = None,
) -> Bus:
    row = await get_bus(session, ctx, bus_id)
    if row.status == "retired":
        raise ConflictError("Retired buses cannot be updated")
    if registration_number is not None:
        registration_number = registration_number.strip()
        if not registration_number:
            raise ValidationFailed("Registration number is required")
        row.registration_number = registration_number
    if fleet_number is not None:
        row.fleet_number = fleet_number.strip() if fleet_number else None
    if display_name is not None:
        if not display_name.strip():
            raise ValidationFailed("Display name is required")
        row.display_name = display_name.strip()
    if capacity is not None:
        _validate_capacity(capacity)
        row.capacity = capacity
    row.updated_at = utcnow()
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Bus registration or fleet number already exists") from exc
    await _audit(
        session,
        ctx,
        action="bus.updated",
        resource_type="bus",
        resource_id=row.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic="bus.updated",
        idempotency_key=f"bus.updated:{row.id}:{row.updated_at.isoformat()}",
        payload={"bus_id": str(row.id)},
        request_id=request_id,
    )
    return row


async def _transition_bus(
    session: AsyncSession,
    ctx: TenantContext,
    bus_id: UUID,
    *,
    new_status: str,
    audit_action: str,
    outbox_topic: str | None,
    request_id: str | None,
) -> Bus:
    row = await get_bus(session, ctx, bus_id)
    try:
        assert_bus_status_transition(row.status, new_status)
    except ValueError as exc:
        raise _validation_from_value_error(exc) from exc
    row.status = new_status
    row.updated_at = utcnow()
    await session.flush()
    await _audit(
        session,
        ctx,
        action=audit_action,
        resource_type="bus",
        resource_id=row.id,
        request_id=request_id,
        metadata={"status": new_status},
    )
    if outbox_topic is not None:
        await _outbox(
            session,
            ctx,
            topic=outbox_topic,
            idempotency_key=f"{outbox_topic}:{row.id}:{row.updated_at.isoformat()}",
            payload={"bus_id": str(row.id), "status": new_status},
            request_id=request_id,
        )
    return row


async def deactivate_bus(
    session: AsyncSession,
    ctx: TenantContext,
    bus_id: UUID,
    *,
    request_id: str | None = None,
) -> Bus:
    return await _transition_bus(
        session,
        ctx,
        bus_id,
        new_status="inactive",
        audit_action="bus.deactivated",
        outbox_topic="bus.updated",
        request_id=request_id,
    )


async def mark_bus_maintenance(
    session: AsyncSession,
    ctx: TenantContext,
    bus_id: UUID,
    *,
    request_id: str | None = None,
) -> Bus:
    return await _transition_bus(
        session,
        ctx,
        bus_id,
        new_status="maintenance",
        audit_action="bus.maintenance",
        outbox_topic="bus.updated",
        request_id=request_id,
    )


async def reactivate_bus(
    session: AsyncSession,
    ctx: TenantContext,
    bus_id: UUID,
    *,
    request_id: str | None = None,
) -> Bus:
    row = await get_bus(session, ctx, bus_id)
    if row.status not in {"inactive", "maintenance"}:
        raise ValidationFailed("Only inactive or maintenance buses can be reactivated")
    return await _transition_bus(
        session,
        ctx,
        bus_id,
        new_status="active",
        audit_action="bus.updated",
        outbox_topic="bus.updated",
        request_id=request_id,
    )


async def retire_bus(
    session: AsyncSession,
    ctx: TenantContext,
    bus_id: UUID,
    *,
    request_id: str | None = None,
) -> Bus:
    return await _transition_bus(
        session,
        ctx,
        bus_id,
        new_status="retired",
        audit_action="bus.retired",
        outbox_topic="bus.retired",
        request_id=request_id,
    )


async def get_route(session: AsyncSession, ctx: TenantContext, route_id: UUID) -> Route:
    row = await session.get(Route, route_id)
    if row is None:
        raise NotFoundError()
    return row


async def create_route(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    name: str,
    code: str,
    direction: str,
    request_id: str | None = None,
) -> Route:
    tenant_id = _require_tenant(ctx)
    if direction not in VALID_ROUTE_DIRECTIONS:
        raise ValidationFailed("Invalid route direction")
    code = code.strip()
    if not code:
        raise ValidationFailed("Route code is required")
    if not name.strip():
        raise ValidationFailed("Route name is required")
    row = Route(
        tenant_id=tenant_id,
        name=name.strip(),
        code=code,
        direction=direction,
        status="active",
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Route code already exists") from exc
    await _audit(
        session,
        ctx,
        action="route.created",
        resource_type="route",
        resource_id=row.id,
        request_id=request_id,
        metadata={"code": code},
    )
    await _outbox(
        session,
        ctx,
        topic="route.created",
        idempotency_key=f"route.created:{row.id}",
        payload={"route_id": str(row.id), "code": code},
        request_id=request_id,
    )
    return row


async def update_route(
    session: AsyncSession,
    ctx: TenantContext,
    route_id: UUID,
    *,
    name: str | None = None,
    code: str | None = None,
    direction: str | None = None,
    request_id: str | None = None,
) -> Route:
    row = await get_route(session, ctx, route_id)
    if row.status == "retired":
        raise ConflictError("Retired routes cannot be updated")
    if name is not None:
        if not name.strip():
            raise ValidationFailed("Route name is required")
        row.name = name.strip()
    if code is not None:
        code = code.strip()
        if not code:
            raise ValidationFailed("Route code is required")
        row.code = code
    if direction is not None:
        if direction not in VALID_ROUTE_DIRECTIONS:
            raise ValidationFailed("Invalid route direction")
        row.direction = direction
    row.updated_at = utcnow()
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Route code already exists") from exc
    await _audit(
        session,
        ctx,
        action="route.updated",
        resource_type="route",
        resource_id=row.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic="route.updated",
        idempotency_key=f"route.updated:{row.id}:{row.updated_at.isoformat()}",
        payload={"route_id": str(row.id)},
        request_id=request_id,
    )
    return row


async def _transition_route(
    session: AsyncSession,
    ctx: TenantContext,
    route_id: UUID,
    *,
    new_status: str,
    audit_action: str,
    request_id: str | None,
) -> Route:
    row = await get_route(session, ctx, route_id)
    try:
        assert_route_status_transition(row.status, new_status)
    except ValueError as exc:
        raise _validation_from_value_error(exc) from exc
    row.status = new_status
    row.updated_at = utcnow()
    await session.flush()
    await _audit(
        session,
        ctx,
        action=audit_action,
        resource_type="route",
        resource_id=row.id,
        request_id=request_id,
        metadata={"status": new_status},
    )
    await _outbox(
        session,
        ctx,
        topic="route.updated",
        idempotency_key=f"route.updated:{row.id}:{row.updated_at.isoformat()}",
        payload={"route_id": str(row.id), "status": new_status},
        request_id=request_id,
    )
    return row


async def activate_route(
    session: AsyncSession,
    ctx: TenantContext,
    route_id: UUID,
    *,
    request_id: str | None = None,
) -> Route:
    return await _transition_route(
        session,
        ctx,
        route_id,
        new_status="active",
        audit_action="route.updated",
        request_id=request_id,
    )


async def deactivate_route(
    session: AsyncSession,
    ctx: TenantContext,
    route_id: UUID,
    *,
    request_id: str | None = None,
) -> Route:
    return await _transition_route(
        session,
        ctx,
        route_id,
        new_status="inactive",
        audit_action="route.deactivated",
        request_id=request_id,
    )


async def retire_route(
    session: AsyncSession,
    ctx: TenantContext,
    route_id: UUID,
    *,
    request_id: str | None = None,
) -> Route:
    return await _transition_route(
        session,
        ctx,
        route_id,
        new_status="retired",
        audit_action="route.retired",
        request_id=request_id,
    )


async def get_route_stop(session: AsyncSession, ctx: TenantContext, stop_id: UUID) -> RouteStop:
    row = await session.get(RouteStop, stop_id)
    if row is None:
        raise NotFoundError()
    return row


async def _assert_route_mutable(route: Route) -> None:
    if route.status == "retired":
        raise ConflictError("Retired routes cannot be modified")


async def add_route_stop(
    session: AsyncSession,
    ctx: TenantContext,
    route_id: UUID,
    *,
    name: str,
    sequence: int,
    latitude: Decimal,
    longitude: Decimal,
    geofence_radius_meters: int = 100,
    request_id: str | None = None,
) -> RouteStop:
    tenant_id = _require_tenant(ctx)
    route = await get_route(session, ctx, route_id)
    await _assert_route_mutable(route)
    if sequence <= 0:
        raise ValidationFailed("Sequence must be positive")
    _validate_coordinates(latitude, longitude)
    _validate_geofence(geofence_radius_meters)
    if not name.strip():
        raise ValidationFailed("Stop name is required")
    row = RouteStop(
        tenant_id=tenant_id,
        route_id=route.id,
        name=name.strip(),
        sequence=sequence,
        latitude=latitude,
        longitude=longitude,
        geofence_radius_meters=geofence_radius_meters,
        status="active",
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Duplicate stop sequence on route") from exc
    await _audit(
        session,
        ctx,
        action="route_stop.created",
        resource_type="route_stop",
        resource_id=row.id,
        request_id=request_id,
        metadata={"route_id": str(route.id), "sequence": sequence},
    )
    return row


async def update_route_stop(
    session: AsyncSession,
    ctx: TenantContext,
    stop_id: UUID,
    *,
    name: str | None = None,
    sequence: int | None = None,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
    geofence_radius_meters: int | None = None,
    request_id: str | None = None,
) -> RouteStop:
    row = await get_route_stop(session, ctx, stop_id)
    route = await get_route(session, ctx, row.route_id)
    await _assert_route_mutable(route)
    if row.status == "retired":
        raise ConflictError("Retired stops cannot be updated")
    if name is not None:
        if not name.strip():
            raise ValidationFailed("Stop name is required")
        row.name = name.strip()
    if sequence is not None:
        if sequence <= 0:
            raise ValidationFailed("Sequence must be positive")
        row.sequence = sequence
    if latitude is not None and longitude is not None:
        _validate_coordinates(latitude, longitude)
        row.latitude = latitude
        row.longitude = longitude
    elif latitude is not None or longitude is not None:
        raise ValidationFailed("Latitude and longitude must be updated together")
    if geofence_radius_meters is not None:
        _validate_geofence(geofence_radius_meters)
        row.geofence_radius_meters = geofence_radius_meters
    row.updated_at = utcnow()
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Duplicate stop sequence on route") from exc
    await _audit(
        session,
        ctx,
        action="route_stop.updated",
        resource_type="route_stop",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def reorder_route_stops(
    session: AsyncSession,
    ctx: TenantContext,
    route_id: UUID,
    *,
    ordered_stop_ids: list[UUID],
    request_id: str | None = None,
) -> list[RouteStop]:
    tenant_id = _require_tenant(ctx)
    route = await get_route(session, ctx, route_id)
    await _assert_route_mutable(route)
    result = await session.execute(
        select(RouteStop)
        .where(RouteStop.tenant_id == tenant_id, RouteStop.route_id == route_id)
        .order_by(RouteStop.sequence)
        .with_for_update()
    )
    stops = list(result.scalars())
    stop_by_id = {stop.id: stop for stop in stops}
    if len(ordered_stop_ids) != len(stops):
        raise ValidationFailed("Reorder must include every stop on the route")
    if set(ordered_stop_ids) != set(stop_by_id):
        raise ValidationFailed("Stop list does not match route stops")
    offset = len(stops) + 1000
    for stop in stops:
        stop.sequence = stop.sequence + offset
    await session.flush()
    for index, stop_id in enumerate(ordered_stop_ids, start=1):
        stop_by_id[stop_id].sequence = index
        stop_by_id[stop_id].updated_at = utcnow()
    await session.flush()
    await _audit(
        session,
        ctx,
        action="route_stop.reordered",
        resource_type="route",
        resource_id=route_id,
        request_id=request_id,
        metadata={"stop_count": len(ordered_stop_ids)},
    )
    return [stop_by_id[stop_id] for stop_id in ordered_stop_ids]


async def deactivate_route_stop(
    session: AsyncSession,
    ctx: TenantContext,
    stop_id: UUID,
    *,
    request_id: str | None = None,
) -> RouteStop:
    row = await get_route_stop(session, ctx, stop_id)
    if row.status != "active":
        raise ValidationFailed("Only active stops can be deactivated")
    row.status = "inactive"
    row.updated_at = utcnow()
    await session.flush()
    await _audit(
        session,
        ctx,
        action="route_stop.deactivated",
        resource_type="route_stop",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def _load_student(session: AsyncSession, ctx: TenantContext, student_id: UUID) -> Student:
    student = await session.get(Student, student_id)
    if student is None:
        raise NotFoundError()
    if student.status == "withdrawn":
        raise ValidationFailed("Student is not eligible for transport assignment")
    return student


async def _load_assignment_stop_on_route(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    route_id: UUID,
    stop_id: UUID,
) -> RouteStop:
    stop = await get_route_stop(session, ctx, stop_id)
    if stop.route_id != route_id:
        raise ValidationFailed("Stop does not belong to the assigned route")
    return stop


async def _assert_no_overlapping_active_assignment(
    session: AsyncSession,
    tenant_id: UUID,
    student_id: UUID,
    effective_from: date,
    effective_to: date | None,
    *,
    exclude_assignment_id: UUID | None = None,
) -> None:
    stmt = select(TransportAssignment).where(
        TransportAssignment.tenant_id == tenant_id,
        TransportAssignment.student_id == student_id,
        TransportAssignment.status == "active",
    )
    if exclude_assignment_id is not None:
        stmt = stmt.where(TransportAssignment.id != exclude_assignment_id)
    rows = list((await session.execute(stmt)).scalars())
    for row in rows:
        if _date_ranges_overlap(row.effective_from, row.effective_to, effective_from, effective_to):
            raise ConflictError("Overlapping active transport assignment")


async def get_transport_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    assignment_id: UUID,
) -> TransportAssignment:
    row = await session.get(TransportAssignment, assignment_id)
    if row is None:
        raise NotFoundError()
    return row


async def get_effective_transport_assignment(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    student_id: UUID,
    at_time: datetime | date,
) -> TransportAssignment | None:
    on_date = _as_effective_date(at_time)
    stmt = (
        select(TransportAssignment)
        .where(
            TransportAssignment.tenant_id == tenant_id,
            TransportAssignment.student_id == student_id,
            TransportAssignment.status == "active",
            TransportAssignment.effective_from <= on_date,
            or_(
                TransportAssignment.effective_to.is_(None),
                TransportAssignment.effective_to >= on_date,
            ),
        )
        .order_by(TransportAssignment.effective_from.desc(), TransportAssignment.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_transport_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    student_id: UUID,
    route_id: UUID,
    stop_id: UUID,
    effective_from: date,
    effective_to: date | None = None,
    request_id: str | None = None,
) -> TransportAssignment:
    tenant_id = _require_tenant(ctx)
    await _load_student(session, ctx, student_id)
    route = await get_route(session, ctx, route_id)
    if route.status != ROUTE_OPERATIONAL_STATUS:
        raise ValidationFailed("Route is not active")
    await _load_assignment_stop_on_route(session, ctx, route_id=route_id, stop_id=stop_id)
    _validate_assignment_dates(effective_from, effective_to)
    await _assert_no_overlapping_active_assignment(
        session,
        tenant_id,
        student_id,
        effective_from,
        effective_to,
    )
    row = TransportAssignment(
        tenant_id=tenant_id,
        student_id=student_id,
        route_id=route_id,
        stop_id=stop_id,
        effective_from=effective_from,
        effective_to=effective_to,
        status="active",
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Transport assignment could not be created") from exc
    await _audit(
        session,
        ctx,
        action="transport_assignment.created",
        resource_type="transport_assignment",
        resource_id=row.id,
        request_id=request_id,
        metadata={"student_id": str(student_id), "route_id": str(route_id)},
    )
    await _outbox(
        session,
        ctx,
        topic="transport_assignment.created",
        idempotency_key=f"transport_assignment.created:{row.id}",
        payload={
            "assignment_id": str(row.id),
            "student_id": str(student_id),
            "route_id": str(route_id),
        },
        request_id=request_id,
    )
    return row


async def update_transport_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    assignment_id: UUID,
    *,
    route_id: UUID | None = None,
    stop_id: UUID | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    request_id: str | None = None,
) -> TransportAssignment:
    row = await get_transport_assignment(session, ctx, assignment_id)
    if row.status in TERMINAL_ASSIGNMENT_STATUSES:
        raise ConflictError("Assignment history is immutable")
    if row.status != "active":
        raise ValidationFailed("Only active assignments can be updated")
    new_route_id = route_id or row.route_id
    new_stop_id = stop_id or row.stop_id
    new_from = effective_from or row.effective_from
    new_to = effective_to if effective_to is not None else row.effective_to
    if route_id is not None:
        route = await get_route(session, ctx, route_id)
        if route.status != ROUTE_OPERATIONAL_STATUS:
            raise ValidationFailed("Route is not active")
    await _load_assignment_stop_on_route(session, ctx, route_id=new_route_id, stop_id=new_stop_id)
    _validate_assignment_dates(new_from, new_to)
    await _assert_no_overlapping_active_assignment(
        session,
        row.tenant_id,
        row.student_id,
        new_from,
        new_to,
        exclude_assignment_id=row.id,
    )
    row.route_id = new_route_id
    row.stop_id = new_stop_id
    row.effective_from = new_from
    row.effective_to = new_to
    row.updated_at = utcnow()
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Transport assignment update conflict") from exc
    await _audit(
        session,
        ctx,
        action="transport_assignment.updated",
        resource_type="transport_assignment",
        resource_id=row.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic="transport_assignment.updated",
        idempotency_key=f"transport_assignment.updated:{row.id}:{row.updated_at.isoformat()}",
        payload={"assignment_id": str(row.id), "student_id": str(row.student_id)},
        request_id=request_id,
    )
    return row


async def suspend_transport_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    assignment_id: UUID,
    *,
    request_id: str | None = None,
) -> TransportAssignment:
    row = await get_transport_assignment(session, ctx, assignment_id)
    if row.status != "active":
        raise ValidationFailed("Only active assignments can be suspended")
    row.status = "suspended"
    row.updated_at = utcnow()
    await session.flush()
    await _audit(
        session,
        ctx,
        action="transport_assignment.suspended",
        resource_type="transport_assignment",
        resource_id=row.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic="transport_assignment.updated",
        idempotency_key=f"transport_assignment.updated:{row.id}:suspended",
        payload={"assignment_id": str(row.id), "status": "suspended"},
        request_id=request_id,
    )
    return row


async def cancel_transport_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    assignment_id: UUID,
    *,
    request_id: str | None = None,
) -> TransportAssignment:
    row = await get_transport_assignment(session, ctx, assignment_id)
    if row.status in TERMINAL_ASSIGNMENT_STATUSES:
        raise ConflictError("Assignment is already closed")
    if row.status not in {"active", "suspended"}:
        raise ValidationFailed("Assignment cannot be cancelled")
    row.status = "cancelled"
    row.updated_at = utcnow()
    await session.flush()
    await _audit(
        session,
        ctx,
        action="transport_assignment.cancelled",
        resource_type="transport_assignment",
        resource_id=row.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic="transport_assignment.updated",
        idempotency_key=f"transport_assignment.updated:{row.id}:cancelled",
        payload={"assignment_id": str(row.id), "status": "cancelled"},
        request_id=request_id,
    )
    return row


async def expire_transport_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    assignment_id: UUID,
    *,
    effective_to: date,
    request_id: str | None = None,
) -> TransportAssignment:
    row = await get_transport_assignment(session, ctx, assignment_id)
    if row.status in TERMINAL_ASSIGNMENT_STATUSES:
        raise ConflictError("Assignment is already closed")
    if row.status not in {"active", "suspended"}:
        raise ValidationFailed("Assignment cannot be expired")
    _validate_assignment_dates(row.effective_from, effective_to)
    row.effective_to = effective_to
    row.status = "expired"
    row.updated_at = utcnow()
    await session.flush()
    await _audit(
        session,
        ctx,
        action="transport_assignment.expired",
        resource_type="transport_assignment",
        resource_id=row.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic="transport_assignment.updated",
        idempotency_key=f"transport_assignment.updated:{row.id}:expired",
        payload={"assignment_id": str(row.id), "status": "expired"},
        request_id=request_id,
    )
    return row


async def _load_staff_profile(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
) -> StaffProfile:
    result = await session.execute(
        select(StaffProfile).where(
            StaffProfile.tenant_id == tenant_id,
            StaffProfile.user_id == user_id,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise ValidationFailed("Staff profile not found for tenant")
    return profile


async def create_transport_attendant(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    user_id: UUID,
    employee_code: str,
    request_id: str | None = None,
) -> TransportAttendant:
    tenant_id = _require_tenant(ctx)
    employee_code = employee_code.strip()
    if not employee_code:
        raise ValidationFailed("Employee code is required")
    await _load_staff_profile(session, tenant_id, user_id)
    row = TransportAttendant(
        tenant_id=tenant_id,
        user_id=user_id,
        employee_code=employee_code,
        status="active",
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Transport attendant already exists for staff member") from exc
    await _audit(
        session,
        ctx,
        action="transport_attendant.created",
        resource_type="transport_attendant",
        resource_id=row.id,
        request_id=request_id,
        metadata={"user_id": str(user_id)},
    )
    return row


async def update_transport_attendant(
    session: AsyncSession,
    ctx: TenantContext,
    attendant_id: UUID,
    *,
    employee_code: str | None = None,
    request_id: str | None = None,
) -> TransportAttendant:
    row = await _get_attendant(session, ctx, attendant_id)
    if employee_code is not None:
        employee_code = employee_code.strip()
        if not employee_code:
            raise ValidationFailed("Employee code is required")
        row.employee_code = employee_code
    row.updated_at = utcnow()
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Employee code already in use") from exc
    await _audit(
        session,
        ctx,
        action="transport_attendant.updated",
        resource_type="transport_attendant",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def _get_attendant(session: AsyncSession, ctx: TenantContext, attendant_id: UUID) -> TransportAttendant:
    row = await session.get(TransportAttendant, attendant_id)
    if row is None:
        raise NotFoundError()
    return row


async def deactivate_transport_attendant(
    session: AsyncSession,
    ctx: TenantContext,
    attendant_id: UUID,
    *,
    request_id: str | None = None,
) -> TransportAttendant:
    row = await _get_attendant(session, ctx, attendant_id)
    if row.status != "active":
        raise ValidationFailed("Attendant is not active")
    row.status = "inactive"
    row.updated_at = utcnow()
    await session.flush()
    await _audit(
        session,
        ctx,
        action="transport_attendant.deactivated",
        resource_type="transport_attendant",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def activate_transport_attendant(
    session: AsyncSession,
    ctx: TenantContext,
    attendant_id: UUID,
    *,
    request_id: str | None = None,
) -> TransportAttendant:
    row = await _get_attendant(session, ctx, attendant_id)
    if row.status != "inactive":
        raise ValidationFailed("Only inactive attendants can be activated")
    row.status = "active"
    row.updated_at = utcnow()
    await session.flush()
    await _audit(
        session,
        ctx,
        action="transport_attendant.updated",
        resource_type="transport_attendant",
        resource_id=row.id,
        request_id=request_id,
        metadata={"status": "active"},
    )
    return row


async def _lock_attendant_for_trip(
    session: AsyncSession,
    tenant_id: UUID,
    attendant_id: UUID,
) -> TransportAttendant:
    result = await session.execute(
        select(TransportAttendant)
        .where(
            TransportAttendant.id == attendant_id,
            TransportAttendant.tenant_id == tenant_id,
        )
        .with_for_update()
    )
    attendant = result.scalar_one_or_none()
    if attendant is None:
        raise NotFoundError()
    return attendant


async def _lock_bus_for_trip(session: AsyncSession, tenant_id: UUID, bus_id: UUID) -> Bus:
    result = await session.execute(
        select(Bus).where(Bus.id == bus_id, Bus.tenant_id == tenant_id).with_for_update()
    )
    bus = result.scalar_one_or_none()
    if bus is None:
        raise NotFoundError()
    return bus


async def _assert_no_conflicting_trips(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    service_date: date,
    bus_id: UUID,
    attendant_id: UUID,
    exclude_trip_id: UUID | None = None,
) -> None:
    stmt = select(Trip).where(
        Trip.tenant_id == tenant_id,
        Trip.service_date == service_date,
        Trip.status.in_(ACTIVE_TRIP_STATUSES),
        or_(Trip.bus_id == bus_id, Trip.attendant_id == attendant_id),
    )
    if exclude_trip_id is not None:
        stmt = stmt.where(Trip.id != exclude_trip_id)
    conflicts = list((await session.execute(stmt.with_for_update())).scalars())
    if conflicts:
        raise ConflictError("Conflicting active trip for bus or attendant")


async def create_trip(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    bus_id: UUID,
    route_id: UUID,
    attendant_id: UUID,
    service_date: date,
    shift: str,
    request_id: str | None = None,
) -> Trip:
    tenant_id = _require_tenant(ctx)
    if shift not in VALID_SHIFTS:
        raise ValidationFailed("Invalid trip shift")
    bus = await _lock_bus_for_trip(session, tenant_id, bus_id)
    if bus.status != BUS_OPERATIONAL_STATUS:
        raise ValidationFailed("Bus is not eligible for trip operations")
    route = await get_route(session, ctx, route_id)
    if route.status != ROUTE_OPERATIONAL_STATUS:
        raise ValidationFailed("Route is not active")
    attendant = await _lock_attendant_for_trip(session, tenant_id, attendant_id)
    if attendant.status != ATTENDANT_OPERATIONAL_STATUS:
        raise ValidationFailed("Attendant is not active")
    await _assert_no_conflicting_trips(
        session,
        tenant_id,
        service_date=service_date,
        bus_id=bus_id,
        attendant_id=attendant_id,
    )
    stops = list(
        (
            await session.execute(
                select(RouteStop)
                .where(
                    RouteStop.tenant_id == tenant_id,
                    RouteStop.route_id == route_id,
                    RouteStop.status == "active",
                )
                .order_by(RouteStop.sequence)
            )
        ).scalars()
    )
    if not stops:
        raise ValidationFailed("Route has no active stops for trip snapshot")
    trip = Trip(
        tenant_id=tenant_id,
        bus_id=bus_id,
        route_id=route_id,
        attendant_id=attendant_id,
        service_date=service_date,
        shift=shift,
        status="scheduled",
    )
    session.add(trip)
    try:
        await session.flush()
        now = utcnow()
        for stop in stops:
            session.add(
                TripStop(
                    tenant_id=tenant_id,
                    trip_id=trip.id,
                    route_stop_id=stop.id,
                    sequence=stop.sequence,
                    name=stop.name,
                    latitude=stop.latitude,
                    longitude=stop.longitude,
                    created_at=now,
                )
            )
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Conflicting active trip for bus or attendant") from exc
    await _audit(
        session,
        ctx,
        action="trip.created",
        resource_type="trip",
        resource_id=trip.id,
        request_id=request_id,
        metadata={
            "bus_id": str(bus_id),
            "route_id": str(route_id),
            "service_date": service_date.isoformat(),
        },
    )
    await _outbox(
        session,
        ctx,
        topic="trip.created",
        idempotency_key=f"trip.created:{trip.id}",
        payload={
            "trip_id": str(trip.id),
            "bus_id": str(bus_id),
            "route_id": str(route_id),
            "service_date": service_date.isoformat(),
        },
        request_id=request_id,
    )
    return trip


async def _get_trip_for_update(session: AsyncSession, ctx: TenantContext, trip_id: UUID) -> Trip:
    tenant_id = _require_tenant(ctx)
    result = await session.execute(
        select(Trip).where(Trip.id == trip_id, Trip.tenant_id == tenant_id).with_for_update()
    )
    trip = result.scalar_one_or_none()
    if trip is None:
        raise NotFoundError()
    return trip


async def start_trip(
    session: AsyncSession,
    ctx: TenantContext,
    trip_id: UUID,
    *,
    request_id: str | None = None,
) -> Trip:
    trip = await _get_trip_for_update(session, ctx, trip_id)
    if trip.status == "boarding":
        return trip
    try:
        assert_trip_status_transition(trip.status, "boarding")
    except ValueError as exc:
        raise _validation_from_value_error(exc) from exc
    now = utcnow()
    trip.status = "boarding"
    trip.started_at = now
    trip.updated_at = now
    await session.flush()
    await _audit(
        session,
        ctx,
        action="trip.started",
        resource_type="trip",
        resource_id=trip.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic="trip.started",
        idempotency_key=f"trip.started:{trip.id}",
        payload={"trip_id": str(trip.id), "status": "boarding"},
        request_id=request_id,
    )
    return trip


async def begin_trip_in_progress(
    session: AsyncSession,
    ctx: TenantContext,
    trip_id: UUID,
    *,
    request_id: str | None = None,
) -> Trip:
    trip = await _get_trip_for_update(session, ctx, trip_id)
    if trip.status == "in_progress":
        return trip
    try:
        assert_trip_status_transition(trip.status, "in_progress")
    except ValueError as exc:
        raise _validation_from_value_error(exc) from exc
    if trip.started_at is None:
        raise ValidationFailed("Trip has not started")
    now = utcnow()
    trip.status = "in_progress"
    trip.updated_at = now
    await session.flush()
    await _audit(
        session,
        ctx,
        action="trip.started",
        resource_type="trip",
        resource_id=trip.id,
        request_id=request_id,
        metadata={"phase": "in_progress"},
    )
    await _outbox(
        session,
        ctx,
        topic="trip.started",
        idempotency_key=f"trip.in_progress:{trip.id}",
        payload={"trip_id": str(trip.id), "status": "in_progress"},
        request_id=request_id,
    )
    return trip


async def complete_trip(
    session: AsyncSession,
    ctx: TenantContext,
    trip_id: UUID,
    *,
    request_id: str | None = None,
) -> Trip:
    trip = await _get_trip_for_update(session, ctx, trip_id)
    if trip.status == "completed":
        return trip
    try:
        assert_trip_status_transition(trip.status, "completed")
    except ValueError as exc:
        raise _validation_from_value_error(exc) from exc
    if trip.started_at is None:
        raise ValidationFailed("Trip has not started")
    now = utcnow()
    if now < trip.started_at:
        raise ValidationFailed("Trip end time is before start time")
    trip.status = "completed"
    trip.ended_at = now
    trip.updated_at = now
    await session.flush()
    await _audit(
        session,
        ctx,
        action="trip.completed",
        resource_type="trip",
        resource_id=trip.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic="trip.completed",
        idempotency_key=f"trip.completed:{trip.id}",
        payload={"trip_id": str(trip.id)},
        request_id=request_id,
    )
    return trip


async def cancel_trip(
    session: AsyncSession,
    ctx: TenantContext,
    trip_id: UUID,
    *,
    request_id: str | None = None,
) -> Trip:
    trip = await _get_trip_for_update(session, ctx, trip_id)
    if trip.status == "cancelled":
        return trip
    try:
        assert_trip_status_transition(trip.status, "cancelled")
    except ValueError as exc:
        raise _validation_from_value_error(exc) from exc
    now = utcnow()
    trip.status = "cancelled"
    trip.ended_at = now
    trip.updated_at = now
    await session.flush()
    await _audit(
        session,
        ctx,
        action="trip.cancelled",
        resource_type="trip",
        resource_id=trip.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic="trip.cancelled",
        idempotency_key=f"trip.cancelled:{trip.id}",
        payload={"trip_id": str(trip.id)},
        request_id=request_id,
    )
    return trip


async def get_trip(session: AsyncSession, ctx: TenantContext, trip_id: UUID) -> Trip:
    row = await session.get(Trip, trip_id)
    if row is None:
        raise NotFoundError()
    return row


async def get_transport_attendant(
    session: AsyncSession,
    ctx: TenantContext,
    attendant_id: UUID,
) -> TransportAttendant:
    return await _get_attendant(session, ctx, attendant_id)


async def list_buses(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    status: str | None,
    search: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[Bus], str | None]:
    _require_tenant(ctx)
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    stmt = select(Bus).order_by(Bus.created_at.desc(), Bus.id.desc())
    if status:
        stmt = stmt.where(Bus.status == status)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Bus.registration_number.ilike(pattern),
                Bus.display_name.ilike(pattern),
                Bus.fleet_number.ilike(pattern),
            )
        )
    decoded = decode_cursor(cursor) if cursor else None
    if decoded:
        created_at, row_id = decoded
        stmt = stmt.where(
            or_(
                Bus.created_at < created_at,
                and_(Bus.created_at == created_at, Bus.id < row_id),
            )
        )
    stmt = stmt.limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(created_at=last.created_at, row_id=last.id)
        rows = rows[:limit]
    return rows, next_cursor


async def list_routes(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    status: str | None,
    direction: str | None,
    search: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[Route], str | None]:
    _require_tenant(ctx)
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    stmt = select(Route).order_by(Route.created_at.desc(), Route.id.desc())
    if status:
        stmt = stmt.where(Route.status == status)
    if direction:
        stmt = stmt.where(Route.direction == direction)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(Route.name.ilike(pattern), Route.code.ilike(pattern)))
    decoded = decode_cursor(cursor) if cursor else None
    if decoded:
        created_at, row_id = decoded
        stmt = stmt.where(
            or_(
                Route.created_at < created_at,
                and_(Route.created_at == created_at, Route.id < row_id),
            )
        )
    stmt = stmt.limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(created_at=last.created_at, row_id=last.id)
        rows = rows[:limit]
    return rows, next_cursor


async def list_route_stops(
    session: AsyncSession,
    ctx: TenantContext,
    route_id: UUID,
) -> list[RouteStop]:
    await get_route(session, ctx, route_id)
    result = await session.execute(
        select(RouteStop).where(RouteStop.route_id == route_id).order_by(RouteStop.sequence.asc())
    )
    return list(result.scalars())


async def list_transport_assignments(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    student_id: UUID | None,
    route_id: UUID | None,
    status: str | None,
    effective_on: date | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[TransportAssignment], str | None]:
    _require_tenant(ctx)
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    stmt = select(TransportAssignment).order_by(
        TransportAssignment.effective_from.desc(),
        TransportAssignment.id.desc(),
    )
    if student_id:
        stmt = stmt.where(TransportAssignment.student_id == student_id)
    if route_id:
        stmt = stmt.where(TransportAssignment.route_id == route_id)
    if status:
        stmt = stmt.where(TransportAssignment.status == status)
    if effective_on:
        stmt = stmt.where(
            TransportAssignment.effective_from <= effective_on,
            or_(
                TransportAssignment.effective_to.is_(None),
                TransportAssignment.effective_to >= effective_on,
            ),
        )
    decoded = decode_cursor(cursor) if cursor else None
    if decoded:
        created_at, row_id = decoded
        stmt = stmt.where(
            or_(
                TransportAssignment.created_at < created_at,
                and_(TransportAssignment.created_at == created_at, TransportAssignment.id < row_id),
            )
        )
    stmt = stmt.limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(created_at=last.created_at, row_id=last.id)
        rows = rows[:limit]
    return rows, next_cursor


async def list_transport_attendants(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    status: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[TransportAttendant], str | None]:
    _require_tenant(ctx)
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    stmt = select(TransportAttendant).order_by(
        TransportAttendant.created_at.desc(),
        TransportAttendant.id.desc(),
    )
    if status:
        stmt = stmt.where(TransportAttendant.status == status)
    decoded = decode_cursor(cursor) if cursor else None
    if decoded:
        created_at, row_id = decoded
        stmt = stmt.where(
            or_(
                TransportAttendant.created_at < created_at,
                and_(TransportAttendant.created_at == created_at, TransportAttendant.id < row_id),
            )
        )
    stmt = stmt.limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(created_at=last.created_at, row_id=last.id)
        rows = rows[:limit]
    return rows, next_cursor


async def list_trips(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    service_date: date | None,
    bus_id: UUID | None,
    route_id: UUID | None,
    attendant_id: UUID | None,
    status: str | None,
    shift: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[Trip], str | None]:
    _require_tenant(ctx)
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    stmt = select(Trip).order_by(Trip.service_date.desc(), Trip.created_at.desc(), Trip.id.desc())
    if service_date:
        stmt = stmt.where(Trip.service_date == service_date)
    if bus_id:
        stmt = stmt.where(Trip.bus_id == bus_id)
    if route_id:
        stmt = stmt.where(Trip.route_id == route_id)
    if attendant_id:
        stmt = stmt.where(Trip.attendant_id == attendant_id)
    if status:
        stmt = stmt.where(Trip.status == status)
    if shift:
        stmt = stmt.where(Trip.shift == shift)
    decoded = decode_cursor(cursor) if cursor else None
    if decoded:
        created_at, row_id = decoded
        stmt = stmt.where(
            or_(
                Trip.created_at < created_at,
                and_(Trip.created_at == created_at, Trip.id < row_id),
            )
        )
    stmt = stmt.limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(created_at=last.created_at, row_id=last.id)
        rows = rows[:limit]
    return rows, next_cursor
