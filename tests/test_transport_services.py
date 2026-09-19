from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from schoolpass.db.session import apply_tenant_context, create_engine, session_factory
from schoolpass.errors import ConflictError, NotFoundError, ValidationFailed
from schoolpass.identity.models import AuditLog, OutboxEvent, StaffProfile
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.models import Trip, TripStop
from schoolpass.transport.services import (
    activate_transport_attendant,
    add_route_stop,
    begin_trip_in_progress,
    cancel_transport_assignment,
    cancel_trip,
    complete_trip,
    create_bus,
    create_route,
    create_transport_assignment,
    create_transport_attendant,
    create_trip,
    deactivate_bus,
    deactivate_transport_attendant,
    expire_transport_assignment,
    get_bus,
    get_effective_transport_assignment,
    mark_bus_maintenance,
    reactivate_bus,
    reorder_route_stops,
    retire_bus,
    retire_route,
    start_trip,
    suspend_transport_assignment,
    update_route_stop,
)


async def _ctx(student_world: dict, tenant_key: str = "tenant_a", admin_key: str = "admin_a") -> TenantContext:
    return TenantContext(
        actor_type="user",
        tenant_id=student_world[tenant_key],
        user_id=student_world[admin_key],
    )


async def _ensure_staff(session, tenant_id, user_id, code: str) -> None:
    existing = (
        await session.execute(
            select(StaffProfile).where(
                StaffProfile.tenant_id == tenant_id,
                StaffProfile.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            StaffProfile(
                tenant_id=tenant_id,
                user_id=user_id,
                staff_type="admin",
                employee_code=code,
            )
        )
        await session.flush()


async def _stack(session, ctx: TenantContext, *, service_date: date = date(2026, 9, 22)) -> dict:
    bus = await create_bus(
        session,
        ctx,
        registration_number=f"KA-{uuid4().hex[:6]}",
        display_name="Stack Bus",
        capacity=40,
        request_id="test",
    )
    route = await create_route(
        session,
        ctx,
        name="Stack Route",
        code=f"R-{uuid4().hex[:4]}",
        direction="pickup",
        request_id="test",
    )
    stop_a = await add_route_stop(
        session,
        ctx,
        route.id,
        name="Stop A",
        sequence=1,
        latitude=Decimal("12.971600"),
        longitude=Decimal("77.594600"),
        request_id="test",
    )
    stop_b = await add_route_stop(
        session,
        ctx,
        route.id,
        name="Stop B",
        sequence=2,
        latitude=Decimal("12.980000"),
        longitude=Decimal("77.600000"),
        request_id="test",
    )
    await _ensure_staff(session, ctx.tenant_id, ctx.user_id, f"ST-{uuid4().hex[:4]}")
    attendant = await create_transport_attendant(
        session,
        ctx,
        user_id=ctx.user_id,
        employee_code=f"ATT-{uuid4().hex[:4]}",
        request_id="test",
    )
    return {
        "bus": bus,
        "route": route,
        "stops": [stop_a, stop_b],
        "attendant": attendant,
        "service_date": service_date,
    }


async def test_bus_lifecycle(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            bus = await create_bus(
                session,
                ctx,
                registration_number="KA-01-TEST-1",
                display_name="Bus One",
                capacity=35,
                request_id="req",
            )
            assert bus.status == "active"
            await deactivate_bus(session, ctx, bus.id, request_id="req")
            assert (await get_bus(session, ctx, bus.id)).status == "inactive"
            await reactivate_bus(session, ctx, bus.id, request_id="req")
            await mark_bus_maintenance(session, ctx, bus.id, request_id="req")
            await reactivate_bus(session, ctx, bus.id, request_id="req")
            await retire_bus(session, ctx, bus.id, request_id="req")
            with pytest.raises(ValidationFailed):
                await reactivate_bus(session, ctx, bus.id, request_id="req")


async def test_retired_bus_cannot_create_trip(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _stack(session, ctx)
            await retire_bus(session, ctx, stack["bus"].id, request_id="req")
            with pytest.raises(ValidationFailed):
                await create_trip(
                    session,
                    ctx,
                    bus_id=stack["bus"].id,
                    route_id=stack["route"].id,
                    attendant_id=stack["attendant"].id,
                    service_date=stack["service_date"],
                    shift="pickup",
                    request_id="req",
                )


async def test_route_lifecycle_and_trip_eligibility(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _stack(session, ctx)
            route = stack["route"]
            from schoolpass.transport.services import deactivate_route

            await deactivate_route(session, ctx, route.id, request_id="req")
            with pytest.raises(ValidationFailed):
                await create_trip(
                    session,
                    ctx,
                    bus_id=stack["bus"].id,
                    route_id=route.id,
                    attendant_id=stack["attendant"].id,
                    service_date=stack["service_date"],
                    shift="pickup",
                    request_id="req",
                )
            await retire_route(session, ctx, route.id, request_id="req")
            with pytest.raises(ValidationFailed):
                await create_trip(
                    session,
                    ctx,
                    bus_id=stack["bus"].id,
                    route_id=route.id,
                    attendant_id=stack["attendant"].id,
                    service_date=stack["service_date"],
                    shift="pickup",
                    request_id="req",
                )


async def test_route_stop_reorder_and_snapshot_immutable(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _stack(session, ctx)
            trip = await create_trip(
                session,
                ctx,
                bus_id=stack["bus"].id,
                route_id=stack["route"].id,
                attendant_id=stack["attendant"].id,
                service_date=stack["service_date"],
                shift="pickup",
                request_id="req",
            )
            snapshot_name = (
                await session.execute(
                    select(TripStop.name).where(TripStop.trip_id == trip.id).order_by(TripStop.sequence)
                )
            ).scalars().all()
            await update_route_stop(
                session,
                ctx,
                stack["stops"][0].id,
                name="Renamed Stop",
                request_id="req",
            )
            after = (
                await session.execute(
                    select(TripStop.name).where(TripStop.trip_id == trip.id).order_by(TripStop.sequence)
                )
            ).scalars().all()
            assert snapshot_name == after
            reordered = await reorder_route_stops(
                session,
                ctx,
                stack["route"].id,
                ordered_stop_ids=[stack["stops"][1].id, stack["stops"][0].id],
                request_id="req",
            )
            assert [stop.sequence for stop in reordered] == [1, 2]


async def test_assignment_overlap_and_effective_lookup(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _stack(session, ctx)
            first = await create_transport_assignment(
                session,
                ctx,
                student_id=student_world["a_student_id"],
                route_id=stack["route"].id,
                stop_id=stack["stops"][0].id,
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 12, 31),
                request_id="req",
            )
            assert first.status == "active"
            with pytest.raises(ConflictError):
                await create_transport_assignment(
                    session,
                    ctx,
                    student_id=student_world["a_student_id"],
                    route_id=stack["route"].id,
                    stop_id=stack["stops"][1].id,
                    effective_from=date(2026, 6, 1),
                    request_id="req",
                )
            effective = await get_effective_transport_assignment(
                session,
                tenant_id=ctx.tenant_id,
                student_id=student_world["a_student_id"],
                at_time=date(2026, 6, 15),
            )
            assert effective is not None and effective.id == first.id
            await suspend_transport_assignment(session, ctx, first.id, request_id="req")
            assert (
                await get_effective_transport_assignment(
                    session,
                    tenant_id=ctx.tenant_id,
                    student_id=student_world["a_student_id"],
                    at_time=date(2026, 6, 15),
                )
            ) is None
            await cancel_transport_assignment(session, ctx, first.id, request_id="req")
            assert first.status == "cancelled"


async def test_assignment_stop_must_match_route(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _stack(session, ctx)
            other_route = await create_route(
                session,
                ctx,
                name="Other",
                code=f"O-{uuid4().hex[:4]}",
                direction="pickup",
                request_id="req",
            )
            other_stop = await add_route_stop(
                session,
                ctx,
                other_route.id,
                name="Other Stop",
                sequence=1,
                latitude=Decimal("12.970000"),
                longitude=Decimal("77.590000"),
                request_id="req",
            )
            with pytest.raises(ValidationFailed):
                await create_transport_assignment(
                    session,
                    ctx,
                    student_id=student_world["a_student_id"],
                    route_id=stack["route"].id,
                    stop_id=other_stop.id,
                    effective_from=date(2026, 1, 1),
                    request_id="req",
                )


async def test_attendant_requires_staff_and_cross_tenant(db_factory, student_world, world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            with pytest.raises(ValidationFailed):
                await create_transport_attendant(
                    session,
                    ctx,
                    user_id=world["user_b"],
                    employee_code="NO-STAFF",
                    request_id="req",
                )
            await _ensure_staff(session, ctx.tenant_id, ctx.user_id, "STAFF-OK")
            attendant = await create_transport_attendant(
                session,
                ctx,
                user_id=ctx.user_id,
                employee_code="ATT-OK",
                request_id="req",
            )
            await deactivate_transport_attendant(session, ctx, attendant.id, request_id="req")
            await activate_transport_attendant(session, ctx, attendant.id, request_id="req")


async def test_trip_lifecycle_and_invalid_transitions(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _stack(session, ctx)
            trip = await create_trip(
                session,
                ctx,
                bus_id=stack["bus"].id,
                route_id=stack["route"].id,
                attendant_id=stack["attendant"].id,
                service_date=stack["service_date"],
                shift="pickup",
                request_id="req",
            )
            assert trip.status == "scheduled"
            assert len(
                (
                    await session.execute(select(TripStop).where(TripStop.trip_id == trip.id))
                ).scalars().all()
            ) == 2
            with pytest.raises(ValidationFailed):
                await complete_trip(session, ctx, trip.id, request_id="req")
            trip = await start_trip(session, ctx, trip.id, request_id="req")
            assert trip.status == "boarding"
            assert trip.started_at is not None
            trip = await begin_trip_in_progress(session, ctx, trip.id, request_id="req")
            assert trip.status == "in_progress"
            trip = await complete_trip(session, ctx, trip.id, request_id="req")
            assert trip.status == "completed"
            with pytest.raises(ValidationFailed):
                await start_trip(session, ctx, trip.id, request_id="req")


async def test_cancel_trip_from_scheduled(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _stack(session, ctx)
            trip = await create_trip(
                session,
                ctx,
                bus_id=stack["bus"].id,
                route_id=stack["route"].id,
                attendant_id=stack["attendant"].id,
                service_date=stack["service_date"],
                shift="pickup",
                request_id="req",
            )
            trip = await cancel_trip(session, ctx, trip.id, request_id="req")
            assert trip.status == "cancelled"
            assert trip.ended_at is not None


async def test_inactive_attendant_rejected(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _stack(session, ctx)
            await deactivate_transport_attendant(session, ctx, stack["attendant"].id, request_id="req")
            with pytest.raises(ValidationFailed):
                await create_trip(
                    session,
                    ctx,
                    bus_id=stack["bus"].id,
                    route_id=stack["route"].id,
                    attendant_id=stack["attendant"].id,
                    service_date=stack["service_date"],
                    shift="pickup",
                    request_id="req",
                )


async def test_conflicting_trips_rejected(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _stack(session, ctx)
            await create_trip(
                session,
                ctx,
                bus_id=stack["bus"].id,
                route_id=stack["route"].id,
                attendant_id=stack["attendant"].id,
                service_date=stack["service_date"],
                shift="pickup",
                request_id="req",
            )
            with pytest.raises(ConflictError):
                await create_trip(
                    session,
                    ctx,
                    bus_id=stack["bus"].id,
                    route_id=stack["route"].id,
                    attendant_id=stack["attendant"].id,
                    service_date=stack["service_date"],
                    shift="dropoff",
                    request_id="req",
                )


async def test_tenant_a_cannot_retire_tenant_b_bus(db_factory, world, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx_b = TenantContext(actor_type="user", tenant_id=world["tenant_b"], user_id=world["user_b"])
            await apply_tenant_context(session, ctx_b)
            bus = await create_bus(
                session,
                ctx_b,
                registration_number=f"TN-{uuid4().hex[:6]}",
                display_name="Tenant B Bus",
                capacity=30,
                request_id="req",
            )
            bus_id = bus.id
    async with db_factory() as session:
        async with session.begin():
            ctx_a = await _ctx(student_world)
            await apply_tenant_context(session, ctx_a)
            with pytest.raises(NotFoundError):
                await retire_bus(session, ctx_a, bus_id, request_id="req")


async def test_trip_create_writes_audit_and_outbox(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _stack(session, ctx)
            trip = await create_trip(
                session,
                ctx,
                bus_id=stack["bus"].id,
                route_id=stack["route"].id,
                attendant_id=stack["attendant"].id,
                service_date=stack["service_date"],
                shift="pickup",
                request_id="corr-trip",
            )
            audit = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.resource_id == trip.id,
                        AuditLog.action == "trip.created",
                    )
                )
            ).scalar_one()
            assert audit.request_id == "corr-trip"
            outbox = (
                await session.execute(
                    select(OutboxEvent).where(
                        OutboxEvent.topic == "trip.created",
                        OutboxEvent.payload["trip_id"].astext == str(trip.id),
                    )
                )
            ).scalar_one()
            assert outbox.published_at is None


async def test_failed_trip_create_rolls_back(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _stack(session, ctx)
            await deactivate_transport_attendant(session, ctx, stack["attendant"].id, request_id="req")
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            trips_before = (
                await session.execute(select(func.count()).select_from(Trip))
            ).scalar_one()
            with pytest.raises(ValidationFailed):
                await create_trip(
                    session,
                    ctx,
                    bus_id=stack["bus"].id,
                    route_id=stack["route"].id,
                    attendant_id=stack["attendant"].id,
                    service_date=stack["service_date"],
                    shift="pickup",
                    request_id="req",
                )
            trips_after = (
                await session.execute(select(func.count()).select_from(Trip))
            ).scalar_one()
            assert trips_before == trips_after


async def test_expire_assignment(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _stack(session, ctx)
            row = await create_transport_assignment(
                session,
                ctx,
                student_id=student_world["a_student_id"],
                route_id=stack["route"].id,
                stop_id=stack["stops"][0].id,
                effective_from=date(2026, 1, 1),
                request_id="req",
            )
            row = await expire_transport_assignment(
                session,
                ctx,
                row.id,
                effective_to=date(2026, 3, 31),
                request_id="req",
            )
            assert row.status == "expired"


async def test_concurrent_trip_start(student_world, settings) -> None:
    engine = create_engine(settings.database_url, null_pool=True)
    factory = session_factory(engine)
    trip_id_holder: dict[str, object] = {}

    async def setup() -> None:
        async with factory() as session:
            async with session.begin():
                ctx = await _ctx(student_world)
                await apply_tenant_context(session, ctx)
                stack = await _stack(session, ctx)
                trip = await create_trip(
                    session,
                    ctx,
                    bus_id=stack["bus"].id,
                    route_id=stack["route"].id,
                    attendant_id=stack["attendant"].id,
                    service_date=stack["service_date"],
                    shift="pickup",
                    request_id="req",
                )
                trip_id_holder["id"] = trip.id

    await setup()

    async def start_once() -> None:
        async with factory() as session:
            async with session.begin():
                ctx = await _ctx(student_world)
                await apply_tenant_context(session, ctx)
                await start_trip(session, ctx, trip_id_holder["id"], request_id="req")

    results = await asyncio.gather(start_once(), start_once(), return_exceptions=True)
    await engine.dispose()
    assert all(not isinstance(r, Exception) for r in results)

    async with factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            from sqlalchemy import func, select

            from schoolpass.identity.models import AuditLog, OutboxEvent

            trip_id = trip_id_holder["id"]
            outbox_count = (
                await session.execute(
                    select(func.count())
                    .select_from(OutboxEvent)
                    .where(
                        OutboxEvent.topic == "trip.started",
                        OutboxEvent.payload["trip_id"].astext == str(trip_id),
                    )
                )
            ).scalar_one()
            audit_count = (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(
                        AuditLog.action == "trip.started",
                        AuditLog.resource_id == trip_id,
                    )
                )
            ).scalar_one()
            assert outbox_count == 1
            assert audit_count == 1
