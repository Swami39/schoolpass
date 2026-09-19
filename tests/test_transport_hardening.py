from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select

from schoolpass.db.session import apply_tenant_context, create_engine, session_factory
from schoolpass.errors import ConflictError, ValidationFailed
from schoolpass.identity.models import AuditLog, OutboxEvent, StaffProfile
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.models import TripStop
from schoolpass.transport.services import (
    activate_route,
    begin_trip_in_progress,
    cancel_trip,
    complete_trip,
    create_bus,
    create_route,
    create_transport_assignment,
    create_trip,
    deactivate_bus,
    get_effective_transport_assignment,
    mark_bus_maintenance,
    reactivate_bus,
    retire_route,
    start_trip,
    update_route_stop,
)


async def _ctx(student_world: dict) -> TenantContext:
    return TenantContext(
        actor_type="user",
        tenant_id=student_world["tenant_a"],
        user_id=student_world["admin_a"],
    )


async def _staff(session, tenant_id, user_id) -> None:
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
                employee_code=f"ST-{uuid4().hex[:4]}",
            )
        )
        await session.flush()


async def _trip_stack(session, ctx: TenantContext, student_world: dict) -> dict:
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
    from schoolpass.transport.services import add_route_stop, create_transport_attendant

    stop = await add_route_stop(
        session,
        ctx,
        route.id,
        name="Stop",
        sequence=1,
        latitude=Decimal("12.971600"),
        longitude=Decimal("77.594600"),
        request_id="test",
    )
    await _staff(session, ctx.tenant_id, ctx.user_id)
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
        "stop": stop,
        "attendant": attendant,
        "service_date": date(2026, 9, 22),
    }


async def test_concurrent_create_trip_same_attendant(student_world, settings) -> None:
    engine = create_engine(settings.database_url, null_pool=True)
    factory = session_factory(engine)
    stack_meta: dict = {}

    async def setup() -> None:
        async with factory() as session:
            async with session.begin():
                ctx = await _ctx(student_world)
                await apply_tenant_context(session, ctx)
                stack = await _trip_stack(session, ctx, student_world)
                bus2 = await create_bus(
                    session,
                    ctx,
                    registration_number=f"KA-{uuid4().hex[:6]}",
                    display_name="Bus 2",
                    capacity=40,
                    request_id="test",
                )
                stack_meta["stack"] = stack
                stack_meta["bus2_id"] = bus2.id

    await setup()

    async def create_for_bus(bus_id) -> None:
        async with factory() as session:
            async with session.begin():
                ctx = await _ctx(student_world)
                await apply_tenant_context(session, ctx)
                stack = stack_meta["stack"]
                await create_trip(
                    session,
                    ctx,
                    bus_id=bus_id,
                    route_id=stack["route"].id,
                    attendant_id=stack["attendant"].id,
                    service_date=stack["service_date"],
                    shift="pickup",
                    request_id="test",
                )

    results = await asyncio.gather(
        create_for_bus(stack_meta["stack"]["bus"].id),
        create_for_bus(stack_meta["bus2_id"]),
        return_exceptions=True,
    )
    await engine.dispose()
    assert sum(1 for r in results if not isinstance(r, Exception)) == 1
    assert sum(1 for r in results if isinstance(r, ConflictError)) == 1


async def test_start_trip_idempotent_no_duplicate_outbox(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _trip_stack(session, ctx, student_world)
            trip = await create_trip(
                session,
                ctx,
                bus_id=stack["bus"].id,
                route_id=stack["route"].id,
                attendant_id=stack["attendant"].id,
                service_date=stack["service_date"],
                shift="pickup",
                request_id="test",
            )
            trip_id = trip.id
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            await start_trip(session, ctx, trip_id, request_id="test")
            await start_trip(session, ctx, trip_id, request_id="test")
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


async def test_failed_create_trip_no_audit_or_outbox(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _trip_stack(session, ctx, student_world)
            await mark_bus_maintenance(session, ctx, stack["bus"].id, request_id="test")
            audit_before = (await session.execute(select(func.count()).select_from(AuditLog))).scalar_one()
            outbox_before = (
                await session.execute(
                    select(func.count()).select_from(OutboxEvent).where(OutboxEvent.topic == "trip.created")
                )
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
                    request_id="test",
                )
            audit_after = (await session.execute(select(func.count()).select_from(AuditLog))).scalar_one()
            outbox_after = (
                await session.execute(
                    select(func.count()).select_from(OutboxEvent).where(OutboxEvent.topic == "trip.created")
                )
            ).scalar_one()
            assert audit_before == audit_after
            assert outbox_before == outbox_after


async def test_trip_stop_snapshot_immutable_after_route_stop_edit(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _trip_stack(session, ctx, student_world)
            trip = await create_trip(
                session,
                ctx,
                bus_id=stack["bus"].id,
                route_id=stack["route"].id,
                attendant_id=stack["attendant"].id,
                service_date=stack["service_date"],
                shift="pickup",
                request_id="test",
            )
            before = (
                await session.execute(
                    select(TripStop.name, TripStop.latitude).where(TripStop.trip_id == trip.id)
                )
            ).all()
            await update_route_stop(
                session,
                ctx,
                stack["stop"].id,
                name="Changed Name",
                latitude=Decimal("13.000000"),
                longitude=Decimal("77.600000"),
                request_id="test",
            )
            after = (
                await session.execute(
                    select(TripStop.name, TripStop.latitude).where(TripStop.trip_id == trip.id)
                )
            ).all()
            assert before == after


async def test_effective_assignment_excludes_non_active(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _trip_stack(session, ctx, student_world)
            from schoolpass.transport.services import (
                cancel_transport_assignment,
                expire_transport_assignment,
                suspend_transport_assignment,
            )

            assignment = await create_transport_assignment(
                session,
                ctx,
                student_id=student_world["a_student_id"],
                route_id=stack["route"].id,
                stop_id=stack["stop"].id,
                effective_from=date(2026, 1, 1),
                request_id="test",
            )
            on_date = date(2026, 6, 1)
            assert (
                await get_effective_transport_assignment(
                    session,
                    tenant_id=ctx.tenant_id,
                    student_id=student_world["a_student_id"],
                    at_time=on_date,
                )
            ) is not None
            await suspend_transport_assignment(session, ctx, assignment.id, request_id="test")
            assert (
                await get_effective_transport_assignment(
                    session,
                    tenant_id=ctx.tenant_id,
                    student_id=student_world["a_student_id"],
                    at_time=on_date,
                )
            ) is None
            assignment2 = await create_transport_assignment(
                session,
                ctx,
                student_id=student_world["a_student_id"],
                route_id=stack["route"].id,
                stop_id=stack["stop"].id,
                effective_from=date(2026, 7, 1),
                request_id="test",
            )
            assert (
                await get_effective_transport_assignment(
                    session,
                    tenant_id=ctx.tenant_id,
                    student_id=student_world["a_student_id"],
                    at_time=date(2026, 7, 15),
                )
            ) is not None
            await cancel_transport_assignment(session, ctx, assignment2.id, request_id="test")
            assert (
                await get_effective_transport_assignment(
                    session,
                    tenant_id=ctx.tenant_id,
                    student_id=student_world["a_student_id"],
                    at_time=date(2026, 7, 15),
                )
            ) is None
            assignment3 = await create_transport_assignment(
                session,
                ctx,
                student_id=student_world["a_student_id"],
                route_id=stack["route"].id,
                stop_id=stack["stop"].id,
                effective_from=date(2026, 8, 1),
                request_id="test",
            )
            await expire_transport_assignment(
                session,
                ctx,
                assignment3.id,
                effective_to=date(2026, 8, 31),
                request_id="test",
            )
            assert (
                await get_effective_transport_assignment(
                    session,
                    tenant_id=ctx.tenant_id,
                    student_id=student_world["a_student_id"],
                    at_time=date(2026, 8, 15),
                )
            ) is None


async def test_maintenance_and_inactive_bus_cannot_create_trip(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _trip_stack(session, ctx, student_world)
            await deactivate_bus(session, ctx, stack["bus"].id, request_id="test")
            with pytest.raises(ValidationFailed):
                await create_trip(
                    session,
                    ctx,
                    bus_id=stack["bus"].id,
                    route_id=stack["route"].id,
                    attendant_id=stack["attendant"].id,
                    service_date=stack["service_date"],
                    shift="pickup",
                    request_id="test",
                )
            await reactivate_bus(session, ctx, stack["bus"].id, request_id="test")
            await mark_bus_maintenance(session, ctx, stack["bus"].id, request_id="test")
            with pytest.raises(ValidationFailed):
                await create_trip(
                    session,
                    ctx,
                    bus_id=stack["bus"].id,
                    route_id=stack["route"].id,
                    attendant_id=stack["attendant"].id,
                    service_date=stack["service_date"],
                    shift="pickup",
                    request_id="test",
                )


async def test_retired_route_cannot_activate_or_create_trip(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _trip_stack(session, ctx, student_world)
            await retire_route(session, ctx, stack["route"].id, request_id="test")
            with pytest.raises(ValidationFailed):
                await activate_route(session, ctx, stack["route"].id, request_id="test")
            with pytest.raises(ValidationFailed):
                await create_trip(
                    session,
                    ctx,
                    bus_id=stack["bus"].id,
                    route_id=stack["route"].id,
                    attendant_id=stack["attendant"].id,
                    service_date=stack["service_date"],
                    shift="pickup",
                    request_id="test",
                )


async def test_completed_trip_lifecycle_terminal(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            stack = await _trip_stack(session, ctx, student_world)
            trip = await create_trip(
                session,
                ctx,
                bus_id=stack["bus"].id,
                route_id=stack["route"].id,
                attendant_id=stack["attendant"].id,
                service_date=stack["service_date"],
                shift="pickup",
                request_id="test",
            )
            trip = await start_trip(session, ctx, trip.id, request_id="test")
            trip = await begin_trip_in_progress(session, ctx, trip.id, request_id="test")
            trip = await complete_trip(session, ctx, trip.id, request_id="test")
            with pytest.raises(ValidationFailed):
                await start_trip(session, ctx, trip.id, request_id="test")
            with pytest.raises(ValidationFailed):
                await cancel_trip(session, ctx, trip.id, request_id="test")
            again = await complete_trip(session, ctx, trip.id, request_id="test")
            assert again.status == "completed"


async def test_list_buses_respects_max_page_size(db_factory, student_world) -> None:
    from schoolpass.transport.services import list_buses

    async with db_factory() as session:
        async with session.begin():
            ctx = await _ctx(student_world)
            await apply_tenant_context(session, ctx)
            for idx in range(3):
                await create_bus(
                    session,
                    ctx,
                    registration_number=f"KA-PAGE-{idx}-{uuid4().hex[:4]}",
                    display_name=f"Bus {idx}",
                    capacity=30,
                    request_id="test",
                )
            rows, cursor = await list_buses(
                session,
                ctx,
                status=None,
                search=None,
                limit=500,
                cursor=None,
            )
            assert len(rows) <= 200
            assert cursor is None or isinstance(cursor, str)


def test_migration_0007_downgrade_upgrade(settings) -> None:
    cfg = Config("alembic.ini")
    try:
        command.downgrade(cfg, "0006_transport_domain")
        command.upgrade(cfg, "head")
    finally:
        command.upgrade(cfg, "head")
