from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import AsyncClient
from sqlalchemy import func, select

from nfc_helpers import NfcWorld, build_nfc_world, nfc_headers, sync_payload
from schoolpass.auth.tokens import encode_access_token
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import AuditLog, ClientDevice, OutboxEvent
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.models import TransportBoardingRecord
from schoolpass.transport.nfc_sync import HEADER_CLIENT_DEVICE, sync_transport_nfc_event


@pytest.fixture
async def nfc_world(db_factory, student_world, settings) -> NfcWorld:
    return await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")


async def _sync(client: AsyncClient, world: NfcWorld, **kwargs) -> dict:
    token = kwargs.pop("token", None)
    response = await client.post(
        "/api/v1/transport/nfc/events/sync",
        json=sync_payload(world, **kwargs),
        headers=nfc_headers(world, token),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_successful_boarding(client: AsyncClient, nfc_world: NfcWorld) -> None:
    body = await _sync(client, nfc_world)
    assert body["result"] == "processed"
    assert body["boarding_record_id"] is not None
    assert body["occurred_at"] != body["received_at"] or True


async def test_successful_dropoff(db_factory, student_world, settings, client: AsyncClient) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="in_progress")
    t0 = datetime.now(tz=UTC)
    await _sync(client, world, event_type="boarding", occurred_at=t0, client_event_id=uuid4())
    body = await _sync(
        client,
        world,
        event_type="dropoff",
        occurred_at=t0 + timedelta(minutes=2),
        client_event_id=uuid4(),
    )
    assert body["result"] == "processed"


async def test_duplicate_client_event(client: AsyncClient, nfc_world: NfcWorld) -> None:
    event_id = uuid4()
    first = await _sync(client, nfc_world, client_event_id=event_id)
    second = await _sync(client, nfc_world, client_event_id=event_id)
    assert first["result"] == "processed"
    assert second["result"] == "duplicate"
    assert second["boarding_record_id"] == first["boarding_record_id"]


async def test_duplicate_no_extra_audit(client: AsyncClient, nfc_world: NfcWorld, db_factory) -> None:
    event_id = uuid4()
    first = await _sync(client, nfc_world, client_event_id=event_id)
    await _sync(client, nfc_world, client_event_id=event_id)
    boarding_id = first["boarding_record_id"]
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=nfc_world.tenant_id, user_id=nfc_world.attendant_user_id),
            )
            audit_count = (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(
                        AuditLog.action == "transport.boarding.recorded",
                        AuditLog.resource_id == boarding_id,
                    )
                )
            ).scalar_one()
            outbox_count = (
                await session.execute(
                    select(func.count())
                    .select_from(OutboxEvent)
                    .where(
                        OutboxEvent.topic == "transport.boarding.recorded",
                        OutboxEvent.payload["boarding_record_id"].astext == str(boarding_id),
                    )
                )
            ).scalar_one()
            assert audit_count == 1
            assert outbox_count == 1


async def test_unknown_card(client: AsyncClient, nfc_world: NfcWorld) -> None:
    body = await _sync(client, nfc_world, card_uid="UNKNOWN999")
    assert body["result"] == "rejected"
    assert body["rejection_code"] == "unknown_card"


async def test_no_transport_assignment(client: AsyncClient, db_factory, student_world, settings) -> None:
    world = await build_nfc_world(db_factory, student_world, settings)
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=student_world["admin_a"]),
            )
            from schoolpass.transport.services import cancel_transport_assignment

            await cancel_transport_assignment(
                session,
                TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=student_world["admin_a"]),
                world.transport_assignment_id,
                request_id="test",
            )
    body = await _sync(client, world)
    assert body["rejection_code"] == "no_transport_assignment"


async def test_route_mismatch(client: AsyncClient, db_factory, student_world, settings) -> None:
    world = await build_nfc_world(db_factory, student_world, settings)
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=student_world["admin_a"])
            await apply_tenant_context(session, ctx)
            from decimal import Decimal

            from schoolpass.transport.models import TransportAttendant
            from schoolpass.transport.services import (
                add_route_stop,
                create_route,
                create_trip,
                start_trip,
            )

            route2 = await create_route(
                session, ctx, name="Other", code=f"X-{uuid4().hex[:4]}", direction="pickup", request_id="t"
            )
            await add_route_stop(
                session,
                ctx,
                route2.id,
                name="S",
                sequence=1,
                latitude=Decimal("12.97"),
                longitude=Decimal("77.59"),
                request_id="t",
            )
            att = (
                await session.execute(
                    select(TransportAttendant).where(TransportAttendant.user_id == world.attendant_user_id)
                )
            ).scalar_one()
            trip2 = await create_trip(
                session,
                ctx,
                bus_id=world.bus_id,
                route_id=route2.id,
                attendant_id=att.id,
                service_date=datetime.now(tz=UTC).date() + timedelta(days=1),
                shift="pickup",
                request_id="t",
            )
            trip2 = await start_trip(session, ctx, trip2.id, request_id="t")
            trip2_id = trip2.id
    body = await _sync(client, world, trip_id=trip2_id)
    assert body["rejection_code"] == "route_mismatch"


async def test_wrong_attendant(client: AsyncClient, nfc_world: NfcWorld) -> None:
    headers = {
        "Authorization": f"Bearer {nfc_world.other_attendant_token}",
        HEADER_CLIENT_DEVICE: str(nfc_world.other_device_id),
    }
    response = await client.post(
        "/api/v1/transport/nfc/events/sync",
        json=sync_payload(nfc_world),
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["rejection_code"] == "unauthorized_attendant"


async def test_wrong_device(client: AsyncClient, nfc_world: NfcWorld) -> None:
    headers = nfc_headers(nfc_world)
    headers[HEADER_CLIENT_DEVICE] = str(uuid4())
    response = await client.post(
        "/api/v1/transport/nfc/events/sync",
        json=sync_payload(nfc_world),
        headers=headers,
    )
    assert response.status_code == 401


async def test_inactive_device(client: AsyncClient, nfc_world: NfcWorld, db_factory) -> None:
    async with db_factory() as session:
        async with session.begin():
            device = await session.get(ClientDevice, nfc_world.client_device_id)
            assert device is not None
            device.status = "inactive"
    response = await client.post(
        "/api/v1/transport/nfc/events/sync",
        json=sync_payload(nfc_world),
        headers=nfc_headers(nfc_world),
    )
    assert response.status_code == 401


async def test_scheduled_trip_rejected(db_factory, student_world, settings, client: AsyncClient) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="scheduled")
    body = await _sync(client, world)
    assert body["rejection_code"] == "trip_not_started"


async def test_completed_trip_historical_accept(
    db_factory, student_world, settings, client: AsyncClient
) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="in_progress")
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=world.attendant_user_id)
            await apply_tenant_context(session, ctx)
            from schoolpass.transport.models import Trip
            from schoolpass.transport.services import complete_trip

            trip = await session.get(Trip, world.trip_id)
            assert trip is not None
            from schoolpass.db.mixins import utcnow

            occurred = utcnow()
            trip.started_at = occurred - timedelta(minutes=10)
            await session.flush()
            await complete_trip(session, ctx, world.trip_id, request_id="t")
    body = await _sync(client, world, occurred_at=occurred)
    assert body["result"] == "processed"


async def test_outside_trip_window(db_factory, student_world, settings, client: AsyncClient) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=world.attendant_user_id)
            await apply_tenant_context(session, ctx)
            from schoolpass.transport.models import Trip

            trip = await session.get(Trip, world.trip_id)
            assert trip is not None and trip.started_at is not None
            too_early = trip.started_at - timedelta(hours=1)
    body = await _sync(client, world, occurred_at=too_early)
    assert body["rejection_code"] == "invalid_event_window"


async def test_cross_tenant_trip_not_found(
    client: AsyncClient, db_factory, student_world, settings
) -> None:
    world_a = await build_nfc_world(db_factory, student_world, settings)
    trip_b_id = uuid4()
    async with db_factory() as session:
        async with session.begin():
            ctx_b = TenantContext(
                actor_type="user", tenant_id=student_world["tenant_b"], user_id=student_world["admin_b"]
            )
            await apply_tenant_context(session, ctx_b)
            from decimal import Decimal

            from schoolpass.identity.models import StaffProfile
            from schoolpass.transport.services import (
                add_route_stop,
                create_bus,
                create_route,
                create_transport_attendant,
                create_trip,
            )

            session.add(
                StaffProfile(
                    tenant_id=student_world["tenant_b"],
                    user_id=student_world["admin_b"],
                    staff_type="admin",
                    employee_code=f"BST-{uuid4().hex[:4]}",
                )
            )
            await session.flush()
            bus = await create_bus(
                session,
                ctx_b,
                registration_number=f"KB-{uuid4().hex[:6]}",
                display_name="B Bus",
                capacity=30,
                request_id="t",
            )
            route = await create_route(
                session, ctx_b, name="B Route", code=f"BR-{uuid4().hex[:4]}", direction="pickup", request_id="t"
            )
            await add_route_stop(
                session,
                ctx_b,
                route.id,
                name="S",
                sequence=1,
                latitude=Decimal("12.97"),
                longitude=Decimal("77.59"),
                request_id="t",
            )
            att = await create_transport_attendant(
                session,
                ctx_b,
                user_id=student_world["admin_b"],
                employee_code=f"BATT-{uuid4().hex[:4]}",
                request_id="t",
            )
            trip = await create_trip(
                session,
                ctx_b,
                bus_id=bus.id,
                route_id=route.id,
                attendant_id=att.id,
                service_date=datetime.now(tz=UTC).date(),
                shift="pickup",
                request_id="t",
            )
            trip_b_id = trip.id
    headers = nfc_headers(world_a)
    payload = sync_payload(world_a, trip_id=trip_b_id)
    response = await client.post(
        "/api/v1/transport/nfc/events/sync",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["rejection_code"] == "invalid_trip"


async def test_teacher_cannot_sync(client: AsyncClient, nfc_world: NfcWorld, db_factory, student_world, settings):
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session, TenantContext(actor_type="system", tenant_id=None, user_id=None)
            )
            from sqlalchemy import select

            from schoolpass.auth.passwords import hash_password
            from schoolpass.identity.models import Role, TenantMembership, User

            role = (await session.execute(select(Role).where(Role.name == "teacher"))).scalar_one()
            user = User(
                id=uuid4(),
                email=f"teacher-{uuid4().hex[:6]}@example.invalid",
                password_hash=hash_password("x"),
            )
            session.add(user)
            await session.flush()
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=nfc_world.tenant_id, user_id=user.id),
            )
            session.add(
                TenantMembership(tenant_id=nfc_world.tenant_id, user_id=user.id, role_id=role.id)
            )
            teacher_id = user.id
    token = encode_access_token(
        settings,
        user_id=teacher_id,
        tenant_id=nfc_world.tenant_id,
        roles=["teacher"],
        mfa=False,
        platform=False,
    )
    response = await client.post(
        "/api/v1/transport/nfc/events/sync",
        json=sync_payload(nfc_world),
        headers={"Authorization": f"Bearer {token}", HEADER_CLIENT_DEVICE: str(nfc_world.client_device_id)},
    )
    assert response.status_code == 403


async def test_parent_cannot_sync(client: AsyncClient, nfc_world: NfcWorld, db_factory, settings):
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session, TenantContext(actor_type="system", tenant_id=None, user_id=None)
            )
            from sqlalchemy import select

            from schoolpass.auth.passwords import hash_password
            from schoolpass.identity.models import Role, TenantMembership, User

            role = (await session.execute(select(Role).where(Role.name == "parent"))).scalar_one()
            user = User(
                id=uuid4(),
                email=f"parent-{uuid4().hex[:6]}@example.invalid",
                password_hash=hash_password("x"),
            )
            session.add(user)
            await session.flush()
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=nfc_world.tenant_id, user_id=user.id),
            )
            session.add(
                TenantMembership(tenant_id=nfc_world.tenant_id, user_id=user.id, role_id=role.id)
            )
            parent_id = user.id
    token = encode_access_token(
        settings,
        user_id=parent_id,
        tenant_id=nfc_world.tenant_id,
        roles=["parent"],
        mfa=False,
        platform=False,
    )
    response = await client.post(
        "/api/v1/transport/nfc/events/sync",
        json=sync_payload(nfc_world),
        headers={"Authorization": f"Bearer {token}", HEADER_CLIENT_DEVICE: str(nfc_world.client_device_id)},
    )
    assert response.status_code == 403


async def test_distinct_events_distinct_records(client: AsyncClient, nfc_world: NfcWorld, db_factory) -> None:
    await _sync(client, nfc_world, client_event_id=uuid4(), device_sequence=1)
    await _sync(client, nfc_world, client_event_id=uuid4(), device_sequence=2)
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=nfc_world.tenant_id, user_id=nfc_world.attendant_user_id),
            )
            count = (
                await session.execute(select(func.count()).select_from(TransportBoardingRecord))
            ).scalar_one()
            assert count == 2


async def test_rejected_retry_same_result(client: AsyncClient, nfc_world: NfcWorld) -> None:
    event_id = uuid4()
    first = await _sync(client, nfc_world, card_uid="BADUID", client_event_id=event_id)
    second = await _sync(client, nfc_world, card_uid="BADUID", client_event_id=event_id)
    assert first["result"] == "rejected"
    assert second["result"] == "rejected"
    assert first["rejection_code"] == second["rejection_code"]


async def test_historical_card_resolution(db_factory, student_world, settings, client: AsyncClient) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")
    old_uid = world.card_uid
    before_replace = datetime.now(tz=UTC) - timedelta(hours=2)
    await _sync(client, world, card_uid=old_uid, occurred_at=before_replace, client_event_id=uuid4())
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=student_world["admin_a"])
            await apply_tenant_context(session, ctx)
            from schoolpass.cards.models import CardAssignment
            from schoolpass.cards.services import register_card, replace_assignment

            active = (
                await session.execute(
                    select(CardAssignment).where(
                        CardAssignment.tenant_id == world.tenant_id,
                        CardAssignment.student_id == world.student_id,
                        CardAssignment.status == "active",
                    )
                )
            ).scalar_one()
            new_card = await register_card(
                session,
                ctx,
                hf_uid=f"04NEW{uuid4().hex[:4].upper()}",
                uhf_epc=None,
                uhf_tid=None,
                profile="uid_only",
                manufactured_at=None,
                request_id="t",
            )
            await replace_assignment(
                session,
                ctx,
                active.id,
                new_physical_card_id=new_card.id,
                new_card_fields=None,
                activate=True,
                revoke_reason="replaced",
                request_id="t",
            )
    after_replace = datetime.now(tz=UTC) + timedelta(days=1)
    body = await _sync(client, world, card_uid=old_uid, occurred_at=after_replace, client_event_id=uuid4())
    assert body["result"] == "rejected"


async def test_rls_cross_tenant_boarding(
    client: AsyncClient, db_factory, student_world, settings
) -> None:
    world = await build_nfc_world(db_factory, student_world, settings)
    await _sync(client, world)
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=student_world["tenant_b"], user_id=student_world["admin_b"]),
            )
            rows = (
                await session.execute(
                    select(TransportBoardingRecord).where(TransportBoardingRecord.tenant_id == world.tenant_id)
                )
            ).scalars().all()
            assert rows == []


async def test_concurrent_duplicate_sync(student_world, settings, db_factory) -> None:
    world = await build_nfc_world(db_factory, student_world, settings)
    event_id = uuid4()

    async def once() -> None:
        async with db_factory() as session:
            async with session.begin():
                ctx = TenantContext(
                    actor_type="user", tenant_id=world.tenant_id, user_id=world.attendant_user_id
                )
                await apply_tenant_context(session, ctx)
                await sync_transport_nfc_event(
                    session,
                    ctx,
                    client_device_id=world.client_device_id,
                    client_event_id=event_id,
                    event_type="boarding",
                    card_uid=world.card_uid,
                    occurred_at=datetime.now(tz=UTC),
                    trip_id=world.trip_id,
                    request_id="test",
                )

    await asyncio.gather(once(), once(), return_exceptions=True)
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=world.attendant_user_id),
            )
            boarding_count = (
                await session.execute(select(func.count()).select_from(TransportBoardingRecord))
            ).scalar_one()
            assert boarding_count == 1


def test_migration_0008_downgrade_upgrade(settings: Settings) -> None:
    cfg = Config("alembic.ini")
    try:
        command.downgrade(cfg, "0007_transport_trip_hardening")
        command.upgrade(cfg, "head")
    finally:
        command.upgrade(cfg, "head")
