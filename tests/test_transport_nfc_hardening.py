from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select

from nfc_helpers import NfcWorld, build_nfc_world, nfc_headers, sync_payload
from schoolpass.db.mixins import utcnow
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import AuditLog, OutboxEvent
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.models import TransportBoardingRecord, Trip
from schoolpass.transport.nfc_sync import (
    REJECTION_INVALID_EVENT_WINDOW,
    _trip_phase_rejection,
    _trip_window_rejection,
)


def test_trip_window_inclusive_boundaries() -> None:
    started = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    ended = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    trip = Trip(
        tenant_id=uuid4(),
        bus_id=uuid4(),
        route_id=uuid4(),
        attendant_id=uuid4(),
        service_date=started.date(),
        shift="pickup",
        status="completed",
        started_at=started,
        ended_at=ended,
    )
    assert _trip_window_rejection(trip, started) is None
    assert _trip_window_rejection(trip, ended) is None
    assert _trip_window_rejection(trip, started - timedelta(seconds=1)) == REJECTION_INVALID_EVENT_WINDOW
    assert _trip_window_rejection(trip, ended + timedelta(seconds=1)) == REJECTION_INVALID_EVENT_WINDOW


def test_trip_window_active_without_end() -> None:
    started = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    trip = Trip(
        tenant_id=uuid4(),
        bus_id=uuid4(),
        route_id=uuid4(),
        attendant_id=uuid4(),
        service_date=started.date(),
        shift="pickup",
        status="in_progress",
        started_at=started,
        ended_at=None,
    )
    assert _trip_window_rejection(trip, started + timedelta(hours=2)) is None


def test_trip_phase_dropoff_on_boarding_trip() -> None:
    trip = Trip(
        tenant_id=uuid4(),
        bus_id=uuid4(),
        route_id=uuid4(),
        attendant_id=uuid4(),
        service_date=datetime.now(tz=UTC).date(),
        shift="pickup",
        status="boarding",
        started_at=utcnow(),
        ended_at=None,
    )
    assert _trip_phase_rejection(trip, "dropoff") == "invalid_trip_phase"
    assert _trip_phase_rejection(trip, "boarding") is None


async def _sync(client: AsyncClient, world: NfcWorld, **kwargs) -> dict:
    response = await client.post(
        "/api/v1/transport/nfc/events/sync",
        json=sync_payload(world, **kwargs),
        headers=nfc_headers(world, kwargs.pop("token", None)),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_dropoff_requires_prior_boarding(client: AsyncClient, db_factory, student_world, settings) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="in_progress")
    body = await _sync(client, world, event_type="dropoff")
    assert body["result"] == "rejected"
    assert body["rejection_code"] == "boarding_required"


async def test_dropoff_after_boarding(client: AsyncClient, db_factory, student_world, settings) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="in_progress")
    t0 = datetime.now(tz=UTC)
    await _sync(client, world, event_type="boarding", occurred_at=t0, client_event_id=uuid4())
    body = await _sync(
        client,
        world,
        event_type="dropoff",
        occurred_at=t0 + timedelta(minutes=5),
        client_event_id=uuid4(),
    )
    assert body["result"] == "processed"


async def test_multiple_boardings_allowed(client: AsyncClient, db_factory, student_world, settings) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")
    t0 = datetime.now(tz=UTC)
    await _sync(client, world, client_event_id=uuid4(), occurred_at=t0, device_sequence=1)
    await _sync(
        client,
        world,
        client_event_id=uuid4(),
        occurred_at=t0 + timedelta(seconds=30),
        device_sequence=2,
    )


async def test_cancelled_trip_rejected(client: AsyncClient, db_factory, student_world, settings) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=world.attendant_user_id)
            await apply_tenant_context(session, ctx)
            from schoolpass.transport.services import cancel_trip

            await cancel_trip(session, ctx, world.trip_id, request_id="t")
    body = await _sync(client, world)
    assert body["rejection_code"] == "cancelled_trip"


async def test_rejected_retry_no_duplicate_rejection_audit(
    client: AsyncClient, db_factory, student_world, settings
) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")
    event_id = uuid4()
    first = await _sync(client, world, card_uid="BAD", client_event_id=event_id)
    await _sync(client, world, card_uid="BAD", client_event_id=event_id)
    server_event_id = first["server_event_id"]
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=world.attendant_user_id),
            )
            count = (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(
                        AuditLog.action == "transport.nfc.rejected",
                        AuditLog.resource_id == server_event_id,
                    )
                )
            ).scalar_one()
            outbox = (
                await session.execute(
                    select(func.count())
                    .select_from(OutboxEvent)
                    .where(
                        OutboxEvent.topic == "transport.nfc.rejected",
                        OutboxEvent.payload["client_event_id"].astext == str(server_event_id),
                    )
                )
            ).scalar_one()
            assert count == 1
            assert outbox == 1


async def test_boarding_record_immutable_after_card_replace(
    client: AsyncClient, db_factory, student_world, settings
) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")
    body = await _sync(client, world, client_event_id=uuid4())
    record_id = body["boarding_record_id"]
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=student_world["admin_a"])
            await apply_tenant_context(session, ctx)
            from schoolpass.cards.models import CardAssignment
            from schoolpass.cards.services import register_card, replace_assignment

            before = await session.get(TransportBoardingRecord, record_id)
            assert before is not None
            snapshot = (
                before.student_id,
                before.physical_card_id,
                before.card_assignment_id,
                before.occurred_at,
            )
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
                hf_uid=f"04X{uuid4().hex[:4].upper()}",
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
            after = await session.get(TransportBoardingRecord, record_id)
            assert after is not None
            assert (
                after.student_id,
                after.physical_card_id,
                after.card_assignment_id,
                after.occurred_at,
            ) == snapshot


async def test_delayed_sync_uses_occurred_at_not_received_at(
    client: AsyncClient, db_factory, student_world, settings
) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")
    scan_time = datetime(2026, 6, 15, 9, 30, tzinfo=UTC)
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=world.attendant_user_id)
            await apply_tenant_context(session, ctx)
            trip = await session.get(Trip, world.trip_id)
            assert trip is not None
            trip.started_at = datetime(2026, 6, 15, 9, 0, tzinfo=UTC)
            trip.status = "in_progress"
            from schoolpass.cards.models import CardAssignment

            assignment = (
                await session.execute(
                    select(CardAssignment).where(
                        CardAssignment.tenant_id == world.tenant_id,
                        CardAssignment.student_id == world.student_id,
                        CardAssignment.status == "active",
                    )
                )
            ).scalar_one()
            assignment.issued_at = datetime(2026, 1, 1, tzinfo=UTC)
            assignment.activated_at = datetime(2026, 1, 1, tzinfo=UTC)
            await session.flush()
    body = await _sync(client, world, occurred_at=scan_time, client_event_id=uuid4())
    assert body["result"] == "processed"
    parsed = datetime.fromisoformat(body["occurred_at"].replace("Z", "+00:00"))
    received = datetime.fromisoformat(body["received_at"].replace("Z", "+00:00"))
    assert parsed == scan_time
    assert received >= parsed


async def test_suspended_assignment_rejected(client: AsyncClient, db_factory, student_world, settings) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=student_world["admin_a"])
            await apply_tenant_context(session, ctx)
            from schoolpass.transport.services import suspend_transport_assignment

            await suspend_transport_assignment(
                session, ctx, world.transport_assignment_id, request_id="t"
            )
    body = await _sync(client, world)
    assert body["rejection_code"] == "no_transport_assignment"


async def test_blocked_card_rejected(client: AsyncClient, db_factory, student_world, settings) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(actor_type="user", tenant_id=world.tenant_id, user_id=student_world["admin_a"])
            await apply_tenant_context(session, ctx)
            from schoolpass.cards.models import CardAssignment
            from schoolpass.cards.services import transition_card_status

            assignment = (
                await session.execute(
                    select(CardAssignment).where(
                        CardAssignment.tenant_id == world.tenant_id,
                        CardAssignment.student_id == world.student_id,
                        CardAssignment.status == "active",
                    )
                )
            ).scalar_one()
            await transition_card_status(
                session,
                ctx,
                assignment.physical_card_id,
                new_status="blocked",
                request_id="t",
                audit_action="card.blocked",
                outbox_topic="card.blocked",
            )
    body = await _sync(client, world)
    assert body["rejection_code"] == "card_blocked"


def test_migration_0009_downgrade_upgrade(settings) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    try:
        command.downgrade(cfg, "0008_transport_nfc_attendance")
        command.upgrade(cfg, "head")
    finally:
        command.upgrade(cfg, "head")
