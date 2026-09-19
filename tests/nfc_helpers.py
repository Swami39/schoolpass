"""Shared fixtures for transport NFC integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select

from schoolpass.auth.passwords import hash_password
from schoolpass.auth.tokens import encode_access_token
from schoolpass.cards.services import activate_assignment, create_assignment, register_card
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import ClientDevice, Role, StaffProfile, TenantMembership, User
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.services import (
    add_route_stop,
    begin_trip_in_progress,
    complete_trip,
    create_bus,
    create_route,
    create_transport_assignment,
    create_transport_attendant,
    create_trip,
    start_trip,
)


@dataclass
class NfcWorld:
    tenant_id: UUID
    attendant_user_id: UUID
    attendant_token: str
    client_device_id: UUID
    trip_id: UUID
    bus_id: UUID
    route_id: UUID
    route_stop_id: UUID
    trip_stop_id: UUID | None
    student_id: UUID
    card_uid: str
    transport_assignment_id: UUID
    other_attendant_token: str
    other_device_id: UUID


async def build_nfc_world(
    db_factory,
    student_world: dict,
    settings: Settings,
    *,
    trip_status: str = "boarding",
) -> NfcWorld:
    password = hash_password("nfc-test-password")
    card_uid = f"04{uuid4().hex[:6].upper()}"
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session, TenantContext(actor_type="system", tenant_id=None, user_id=None)
            )
            role = (
                await session.execute(select(Role).where(Role.name == "bus_attendant"))
            ).scalar_one()
            attendant_user = User(
                id=uuid4(),
                email=f"attendant-{uuid4().hex[:6]}@example.invalid",
                password_hash=password,
            )
            other_user = User(
                id=uuid4(),
                email=f"other-att-{uuid4().hex[:6]}@example.invalid",
                password_hash=password,
            )
            session.add_all([attendant_user, other_user])
            await session.flush()
            tenant_id = student_world["tenant_a"]
            ctx_admin = TenantContext(
                actor_type="user", tenant_id=tenant_id, user_id=student_world["admin_a"]
            )
            await apply_tenant_context(session, ctx_admin)
            for user in (attendant_user, other_user):
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
                        user_id=user.id,
                        staff_type="attendant",
                        employee_code=f"ST-{uuid4().hex[:4]}",
                    )
                )
            await session.flush()
            ctx_att = TenantContext(actor_type="user", tenant_id=tenant_id, user_id=attendant_user.id)
            await apply_tenant_context(session, ctx_att)
            bus = await create_bus(
                session,
                ctx_att,
                registration_number=f"KA-{uuid4().hex[:6]}",
                display_name="NFC Bus",
                capacity=40,
                request_id="test",
            )
            route = await create_route(
                session,
                ctx_att,
                name="NFC Route",
                code=f"NR-{uuid4().hex[:4]}",
                direction="pickup",
                request_id="test",
            )
            stop = await add_route_stop(
                session,
                ctx_att,
                route.id,
                name="Main Stop",
                sequence=1,
                latitude=Decimal("12.971600"),
                longitude=Decimal("77.594600"),
                request_id="test",
            )
            attendant = await create_transport_attendant(
                session,
                ctx_att,
                user_id=attendant_user.id,
                employee_code=f"ATT-{uuid4().hex[:4]}",
                request_id="test",
            )
            await create_transport_attendant(
                session,
                ctx_att,
                user_id=other_user.id,
                employee_code=f"ATT-{uuid4().hex[:4]}",
                request_id="test",
            )
            assignment = await create_transport_assignment(
                session,
                ctx_att,
                student_id=student_world["a_student_id"],
                route_id=route.id,
                stop_id=stop.id,
                effective_from=date(2020, 1, 1),
                request_id="test",
            )
            card = await register_card(
                session,
                ctx_att,
                hf_uid=card_uid,
                uhf_epc=None,
                uhf_tid=None,
                profile="uid_only",
                manufactured_at=None,
                request_id="test",
            )
            card_row = await create_assignment(
                session,
                ctx_att,
                student_id=student_world["a_student_id"],
                physical_card_id=card.id,
                request_id="test",
            )
            await activate_assignment(session, ctx_att, card_row.id, request_id="test")
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
            if trip_status in {"boarding", "in_progress", "completed"}:
                trip = await start_trip(session, ctx_att, trip.id, request_id="test")
            if trip_status in {"in_progress", "completed"}:
                trip = await begin_trip_in_progress(session, ctx_att, trip.id, request_id="test")
            if trip_status == "completed":
                trip = await complete_trip(session, ctx_att, trip.id, request_id="test")
            device = ClientDevice(
                user_id=attendant_user.id,
                device_uuid=uuid4(),
                app_flavor="bus_attendant",
                status="active",
            )
            other_device = ClientDevice(
                user_id=other_user.id,
                device_uuid=uuid4(),
                app_flavor="bus_attendant",
                status="active",
            )
            session.add_all([device, other_device])
            await session.flush()
            from schoolpass.transport.models import TripStop

            trip_stop = (
                await session.execute(select(TripStop).where(TripStop.trip_id == trip.id))
            ).scalar_one()
            other_user_id = other_user.id
            attendant_user_id = attendant_user.id
            client_device_id = device.id
            other_device_id = other_device.id
            trip_id = trip.id
            transport_assignment_id = assignment.id
            student_id = student_world["a_student_id"]

    token = encode_access_token(
        settings,
        user_id=attendant_user_id,
        tenant_id=tenant_id,
        roles=["bus_attendant"],
        mfa=False,
        platform=False,
    )
    other_token = encode_access_token(
        settings,
        user_id=other_user_id,
        tenant_id=tenant_id,
        roles=["bus_attendant"],
        mfa=False,
        platform=False,
    )
    return NfcWorld(
        tenant_id=tenant_id,
        attendant_user_id=attendant_user_id,
        attendant_token=token,
        client_device_id=client_device_id,
        trip_id=trip_id,
        bus_id=bus.id,
        route_id=route.id,
        route_stop_id=stop.id,
        trip_stop_id=trip_stop.id,
        student_id=student_id,
        card_uid=card_uid,
        transport_assignment_id=transport_assignment_id,
        other_attendant_token=other_token,
        other_device_id=other_device_id,
    )


def sync_payload(
    world: NfcWorld,
    *,
    client_event_id: UUID | None = None,
    event_type: str = "boarding",
    occurred_at: datetime | None = None,
    device_sequence: int = 1,
    trip_id: UUID | None = None,
    trip_stop_id: UUID | None = None,
    card_uid: str | None = None,
    token: str | None = None,
) -> dict:
    return {
        "client_event_id": str(client_event_id or uuid4()),
        "event_type": event_type,
        "card_uid": card_uid or world.card_uid,
        "occurred_at": (occurred_at or datetime.now(tz=UTC)).isoformat(),
        "device_sequence": device_sequence,
        "trip_id": str(trip_id or world.trip_id),
        "trip_stop_id": str(trip_stop_id) if trip_stop_id else None,
    }


def nfc_headers(world: NfcWorld, token: str | None = None) -> dict[str, str]:
    from schoolpass.transport.nfc_sync import HEADER_CLIENT_DEVICE

    return {
        "Authorization": f"Bearer {token or world.attendant_token}",
        HEADER_CLIENT_DEVICE: str(world.client_device_id),
    }
