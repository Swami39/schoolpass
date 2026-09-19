from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import StaffProfile
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.models import (
    Bus,
    Route,
    RouteStop,
    TransportAssignment,
    TransportAttendant,
    Trip,
    TripStop,
)


async def test_transport_tables_force_rls(engine) -> None:
    for table in (
        "buses",
        "transport_attendants",
        "routes",
        "route_stops",
        "transport_assignments",
        "trips",
        "trip_stops",
    ):
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT relrowsecurity, relforcerowsecurity
                        FROM pg_class WHERE relname = :table
                        """
                    ),
                    {"table": table},
                )
            ).one()
            assert row[0] is True
            assert row[1] is True


async def test_bus_registration_unique_within_tenant(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=student_world["tenant_a"], user_id=student_world["admin_a"]),
            )
            session.add(
                Bus(
                    tenant_id=student_world["tenant_a"],
                    registration_number="KA-01-AB-1234",
                    display_name="Bus 1",
                    capacity=40,
                )
            )
            await session.flush()
            session.add(
                Bus(
                    tenant_id=student_world["tenant_a"],
                    registration_number="KA-01-AB-1234",
                    display_name="Bus 2",
                    capacity=40,
                )
            )
            with pytest.raises(DBAPIError):
                await session.flush()


async def test_route_code_unique_within_tenant(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=student_world["tenant_a"], user_id=student_world["admin_a"]),
            )
            session.add(
                Route(
                    tenant_id=student_world["tenant_a"],
                    name="North Loop",
                    code="N1",
                    direction="pickup",
                )
            )
            await session.flush()
            session.add(
                Route(
                    tenant_id=student_world["tenant_a"],
                    name="North Loop 2",
                    code="N1",
                    direction="dropoff",
                )
            )
            with pytest.raises(DBAPIError):
                await session.flush()


async def test_assignment_stop_must_belong_to_route(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(
                actor_type="user",
                tenant_id=student_world["tenant_a"],
                user_id=student_world["admin_a"],
            )
            await apply_tenant_context(session, ctx)
            route_a = Route(
                tenant_id=student_world["tenant_a"],
                name="Route A",
                code="RA",
                direction="pickup",
            )
            route_b = Route(
                tenant_id=student_world["tenant_a"],
                name="Route B",
                code="RB",
                direction="pickup",
            )
            session.add_all([route_a, route_b])
            await session.flush()
            stop_on_b = RouteStop(
                tenant_id=student_world["tenant_a"],
                route_id=route_b.id,
                name="Stop B1",
                sequence=1,
                latitude=Decimal("12.971600"),
                longitude=Decimal("77.594600"),
            )
            session.add(stop_on_b)
            await session.flush()
            session.add(
                TransportAssignment(
                    tenant_id=student_world["tenant_a"],
                    student_id=student_world["a_student_id"],
                    route_id=route_a.id,
                    stop_id=stop_on_b.id,
                    effective_from=date(2026, 1, 1),
                    status="active",
                )
            )
            with pytest.raises(DBAPIError):
                await session.flush()


async def test_only_one_active_transport_assignment_per_student(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(
                actor_type="user",
                tenant_id=student_world["tenant_a"],
                user_id=student_world["admin_a"],
            )
            await apply_tenant_context(session, ctx)
            route = Route(
                tenant_id=student_world["tenant_a"],
                name="Route C",
                code="RC",
                direction="pickup",
            )
            session.add(route)
            await session.flush()
            stop = RouteStop(
                tenant_id=student_world["tenant_a"],
                route_id=route.id,
                name="Stop C1",
                sequence=1,
                latitude=Decimal("12.971600"),
                longitude=Decimal("77.594600"),
            )
            session.add(stop)
            await session.flush()
            session.add(
                TransportAssignment(
                    tenant_id=student_world["tenant_a"],
                    student_id=student_world["a_student_id"],
                    route_id=route.id,
                    stop_id=stop.id,
                    effective_from=date(2026, 1, 1),
                    status="active",
                )
            )
            await session.flush()
            session.add(
                TransportAssignment(
                    tenant_id=student_world["tenant_a"],
                    student_id=student_world["a_student_id"],
                    route_id=route.id,
                    stop_id=stop.id,
                    effective_from=date(2026, 6, 1),
                    status="active",
                )
            )
            with pytest.raises(DBAPIError):
                await session.flush()


async def test_tenant_a_cannot_read_tenant_b_bus(db_factory, world, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world["tenant_b"], user_id=world["user_b"]),
            )
            session.add(
                Bus(
                    tenant_id=world["tenant_b"],
                    registration_number="TN-99-ZZ-9999",
                    display_name="Tenant B Bus",
                    capacity=30,
                )
            )
            await session.flush()
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world["tenant_a"], user_id=student_world["admin_a"]),
            )
            rows = (await session.execute(select(Bus))).scalars().all()
            assert all(row.tenant_id == world["tenant_a"] for row in rows)


async def test_trip_tenant_integrity(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(
                actor_type="user",
                tenant_id=student_world["tenant_a"],
                user_id=student_world["admin_a"],
            )
            await apply_tenant_context(session, ctx)
            bus = Bus(
                tenant_id=student_world["tenant_a"],
                registration_number="KA-02-CD-5678",
                display_name="Trip Bus",
                capacity=35,
            )
            route = Route(
                tenant_id=student_world["tenant_a"],
                name="Trip Route",
                code="TR1",
                direction="pickup",
            )
            session.add_all([bus, route])
            await session.flush()
            session.add(
                StaffProfile(
                    tenant_id=student_world["tenant_a"],
                    user_id=student_world["admin_a"],
                    staff_type="admin",
                    employee_code="STAFF-ATT-001",
                )
            )
            await session.flush()
            attendant = TransportAttendant(
                tenant_id=student_world["tenant_a"],
                user_id=student_world["admin_a"],
                employee_code="ATT-001",
            )
            session.add(attendant)
            await session.flush()
            trip = Trip(
                tenant_id=student_world["tenant_a"],
                bus_id=bus.id,
                route_id=route.id,
                attendant_id=attendant.id,
                service_date=date(2026, 9, 22),
                shift="pickup",
            )
            session.add(trip)
            await session.flush()
            stop = RouteStop(
                tenant_id=student_world["tenant_a"],
                route_id=route.id,
                name="Snap Stop",
                sequence=1,
                latitude=Decimal("12.971600"),
                longitude=Decimal("77.594600"),
            )
            session.add(stop)
            await session.flush()
            session.add(
                TripStop(
                    tenant_id=student_world["tenant_a"],
                    trip_id=trip.id,
                    route_stop_id=stop.id,
                    sequence=1,
                    name=stop.name,
                    latitude=stop.latitude,
                    longitude=stop.longitude,
                    created_at=datetime.now(UTC),
                )
            )
            await session.flush()


async def test_invalid_latitude_rejected(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=student_world["tenant_a"], user_id=student_world["admin_a"]),
            )
            route = Route(
                tenant_id=student_world["tenant_a"],
                name="Bad Geo",
                code="BG",
                direction="pickup",
            )
            session.add(route)
            await session.flush()
            session.add(
                RouteStop(
                    tenant_id=student_world["tenant_a"],
                    route_id=route.id,
                    name="Bad",
                    sequence=1,
                    latitude=Decimal("120.0"),
                    longitude=Decimal("77.0"),
                )
            )
            with pytest.raises(DBAPIError):
                await session.flush()


def test_migration_downgrade_and_upgrade(settings) -> None:
    cfg = Config("alembic.ini")
    try:
        command.downgrade(cfg, "0005_attendance")
        command.upgrade(cfg, "head")
    finally:
        command.upgrade(cfg, "head")
