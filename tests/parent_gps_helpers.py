"""Fixtures for parent bus location tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select

from schoolpass.auth.passwords import hash_password
from schoolpass.auth.tokens import encode_access_token
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import Role, StaffProfile, TenantMembership, User
from schoolpass.people.models import Guardian, Student
from schoolpass.people.services import attach_guardian
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.gps_redis import TripLastLocation
from schoolpass.transport.services import (
    add_route_stop,
    begin_trip_in_progress,
    cancel_trip,
    complete_trip,
    create_bus,
    create_route,
    create_transport_assignment,
    create_transport_attendant,
    create_trip,
    start_trip,
)


@dataclass
class ParentTransportWorld:
    tenant_id: UUID
    parent_user_id: UUID
    parent_token: str
    other_parent_token: str
    student_id: UUID
    other_child_id: UUID
    tenant_b_student_id: UUID
    trip_id: UUID
    bus_id: UUID
    route_id: UUID
    decoy_trip_id: UUID | None = None


async def build_parent_transport_world(
    db_factory,
    student_world: dict,
    settings: Settings,
    *,
    trip_status: str = "in_progress",
    link_primary_guardian: bool = True,
    assignment_active: bool = True,
    assignment_effective_from: date | None = None,
    guardian_status: str = "active",
    student_guardian_active: bool = True,
    decoy_in_progress_trip: bool = False,
) -> ParentTransportWorld:
    password = hash_password("parent-gps-password")
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session, TenantContext(actor_type="system", tenant_id=None, user_id=None)
            )
            parent_role = (
                await session.execute(select(Role).where(Role.name == "parent"))
            ).scalar_one()
            attendant_role = (
                await session.execute(select(Role).where(Role.name == "bus_attendant"))
            ).scalar_one()
            parent_user = User(
                id=uuid4(),
                email=f"parent-{uuid4().hex[:6]}@example.invalid",
                password_hash=password,
            )
            other_parent = User(
                id=uuid4(),
                email=f"other-parent-{uuid4().hex[:6]}@example.invalid",
                password_hash=password,
            )
            attendant_user = User(
                id=uuid4(),
                email=f"att-{uuid4().hex[:6]}@example.invalid",
                password_hash=password,
            )
            session.add_all([parent_user, other_parent, attendant_user])
            await session.flush()
            tenant_id = student_world["tenant_a"]
            for user, role in (
                (parent_user, parent_role),
                (other_parent, parent_role),
                (attendant_user, attendant_role),
            ):
                await apply_tenant_context(
                    session,
                    TenantContext(actor_type="user", tenant_id=tenant_id, user_id=user.id),
                )
                session.add(
                    TenantMembership(
                        tenant_id=tenant_id,
                        user_id=user.id,
                        role_id=role.id,
                    )
                )
            session.add(
                StaffProfile(
                    tenant_id=tenant_id,
                    user_id=attendant_user.id,
                    staff_type="attendant",
                    employee_code=f"ST-{uuid4().hex[:4]}",
                )
            )
            await session.flush()
            ctx = TenantContext(actor_type="user", tenant_id=tenant_id, user_id=parent_user.id)
            await apply_tenant_context(session, ctx)
            guardian = Guardian(
                tenant_id=tenant_id,
                first_name="Parent",
                last_name="One",
                user_id=parent_user.id,
                status=guardian_status,
            )
            other_guardian = Guardian(
                tenant_id=tenant_id,
                first_name="Parent",
                last_name="Two",
                user_id=other_parent.id,
                status="active",
            )
            session.add_all([guardian, other_guardian])
            await session.flush()
            other_child = Student(
                tenant_id=tenant_id,
                historical_subject_id=uuid4(),
                admission_no=f"OTH-{uuid4().hex[:6]}",
                first_name="Other",
                last_name="Child",
                date_of_birth=date(2015, 5, 5),
            )
            session.add(other_child)
            await session.flush()
            if link_primary_guardian:
                link = await attach_guardian(
                    session,
                    ctx,
                    student_id=student_world["a_student_id"],
                    guardian_id=guardian.id,
                    relationship_type="guardian",
                    is_primary_contact=True,
                    can_receive_notifications=True,
                    can_pay_fees=False,
                    request_id="test",
                )
                if not student_guardian_active:
                    link.status = "inactive"
                    await session.flush()
            await attach_guardian(
                session,
                ctx,
                student_id=other_child.id,
                guardian_id=other_guardian.id,
                relationship_type="guardian",
                is_primary_contact=True,
                can_receive_notifications=True,
                can_pay_fees=False,
                request_id="test",
            )
            ctx_att = TenantContext(actor_type="user", tenant_id=tenant_id, user_id=attendant_user.id)
            await apply_tenant_context(session, ctx_att)
            bus = await create_bus(
                session,
                ctx_att,
                registration_number=f"BUS-{uuid4().hex[:6]}",
                display_name="Test Bus",
                capacity=40,
                request_id="test",
            )
            route = await create_route(
                session,
                ctx_att,
                name="Route A",
                code=f"R-{uuid4().hex[:4]}",
                direction="pickup",
                request_id="test",
            )
            stop = await add_route_stop(
                session,
                ctx_att,
                route_id=route.id,
                name="Stop 1",
                sequence=1,
                latitude=Decimal("12.970000"),
                longitude=Decimal("77.590000"),
                request_id="test",
            )
            attendant = await create_transport_attendant(
                session,
                ctx_att,
                user_id=attendant_user.id,
                employee_code=f"ATT-{uuid4().hex[:4]}",
                request_id="test",
            )
            eff_from = assignment_effective_from or date(2020, 1, 1)
            assignment = await create_transport_assignment(
                session,
                ctx_att,
                student_id=student_world["a_student_id"],
                route_id=route.id,
                stop_id=stop.id,
                effective_from=eff_from,
                request_id="test",
            )
            if not assignment_active:
                assignment.status = "suspended"
                await session.flush()
            service_date = date.today()
            trip = await create_trip(
                session,
                ctx_att,
                bus_id=bus.id,
                route_id=route.id,
                attendant_id=attendant.id,
                service_date=service_date,
                shift="pickup",
                request_id="test",
            )
            if trip_status == "cancelled":
                trip = await cancel_trip(session, ctx_att, trip.id, request_id="test")
            elif trip_status in {"boarding", "in_progress", "completed"}:
                trip = await start_trip(session, ctx_att, trip.id, request_id="test")
            if trip_status in {"in_progress", "completed"}:
                trip = await begin_trip_in_progress(session, ctx_att, trip.id, request_id="test")
            if trip_status == "completed":
                trip = await complete_trip(session, ctx_att, trip.id, request_id="test")

            decoy_trip_id: UUID | None = None
            if decoy_in_progress_trip:
                decoy_user = User(
                    id=uuid4(),
                    email=f"decoy-att-{uuid4().hex[:6]}@example.invalid",
                    password_hash=password,
                )
                session.add(decoy_user)
                await session.flush()
                await apply_tenant_context(
                    session,
                    TenantContext(actor_type="user", tenant_id=tenant_id, user_id=decoy_user.id),
                )
                session.add(
                    TenantMembership(
                        tenant_id=tenant_id,
                        user_id=decoy_user.id,
                        role_id=attendant_role.id,
                    )
                )
                session.add(
                    StaffProfile(
                        tenant_id=tenant_id,
                        user_id=decoy_user.id,
                        staff_type="attendant",
                        employee_code=f"SD-{uuid4().hex[:4]}",
                    )
                )
                await session.flush()
                decoy_attendant = await create_transport_attendant(
                    session,
                    ctx_att,
                    user_id=decoy_user.id,
                    employee_code=f"DATT-{uuid4().hex[:4]}",
                    request_id="test",
                )
                route_b = await create_route(
                    session,
                    ctx_att,
                    name="Route Decoy",
                    code=f"RD-{uuid4().hex[:4]}",
                    direction="pickup",
                    request_id="test",
                )
                await add_route_stop(
                    session,
                    ctx_att,
                    route_id=route_b.id,
                    name="Decoy Stop",
                    sequence=1,
                    latitude=Decimal("12.980000"),
                    longitude=Decimal("77.580000"),
                    request_id="test",
                )
                bus_b = await create_bus(
                    session,
                    ctx_att,
                    registration_number=f"DEC-{uuid4().hex[:6]}",
                    display_name="Decoy Bus",
                    capacity=40,
                    request_id="test",
                )
                decoy = await create_trip(
                    session,
                    ctx_att,
                    bus_id=bus_b.id,
                    route_id=route_b.id,
                    attendant_id=decoy_attendant.id,
                    service_date=service_date,
                    shift="pickup",
                    request_id="test",
                )
                decoy = await start_trip(session, ctx_att, decoy.id, request_id="test")
                decoy = await begin_trip_in_progress(session, ctx_att, decoy.id, request_id="test")
                decoy_trip_id = decoy.id

    token = encode_access_token(
        settings,
        user_id=parent_user.id,
        tenant_id=tenant_id,
        roles=["parent"],
        mfa=False,
        platform=False,
    )
    other_token = encode_access_token(
        settings,
        user_id=other_parent.id,
        tenant_id=tenant_id,
        roles=["parent"],
        mfa=False,
        platform=False,
    )
    return ParentTransportWorld(
        tenant_id=tenant_id,
        parent_user_id=parent_user.id,
        parent_token=token,
        other_parent_token=other_token,
        student_id=student_world["a_student_id"],
        other_child_id=other_child.id,
        tenant_b_student_id=student_world["b_student_id"],
        trip_id=trip.id,
        bus_id=bus.id,
        route_id=route.id,
        decoy_trip_id=decoy_trip_id,
    )


async def seed_redis_trip_location(
    app,
    world: ParentTransportWorld,
    *,
    occurred_at: datetime | None = None,
    trip_id: UUID | None = None,
    bus_id: UUID | None = None,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
) -> None:
    redis = app.state.redis
    tid = trip_id or world.trip_id
    bid = bus_id or world.bus_id
    now = occurred_at or datetime.now(tz=UTC)
    sample = TripLastLocation(
        trip_id=tid,
        bus_id=bid,
        latitude=latitude or Decimal("12.971600"),
        longitude=longitude or Decimal("77.594600"),
        occurred_at=now,
        accuracy_meters=Decimal("15"),
        received_at=datetime.now(tz=UTC),
    )
    await redis.set(f"trip:{tid}:last", sample.to_json(), ex=3600)


async def seed_redis_raw(app, trip_id: UUID, payload: str | bytes) -> None:
    redis = app.state.redis
    await redis.set(f"trip:{trip_id}:last", payload, ex=3600)


FORBIDDEN_PARENT_LOCATION_RESPONSE_KEYS = frozenset(
    {
        "tenant_id",
        "guardian_id",
        "attendant_id",
        "client_device_id",
        "route_id",
        "redis_key",
        "authorization",
    }
)
