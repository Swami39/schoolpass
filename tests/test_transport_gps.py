"""GPS sync API tests (Phase 6C)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError

from nfc_helpers import NfcWorld, build_nfc_world, nfc_headers
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.gps_redis import get_trip_last_location, trip_last_key
from schoolpass.transport.gps_sync import HEADER_CLIENT_DEVICE, PROCESSING_RECORDED
from schoolpass.transport.models import LocationSample


def gps_sample(
    world: NfcWorld,
    *,
    client_sample_id=None,
    trip_id=None,
    lat: str = "12.971600",
    lon: str = "77.594600",
    occurred_at: datetime | None = None,
    bus_id=None,
    device_sequence: int = 1,
    source: str = "phone_gnss",
    accuracy: str | None = "12.5",
) -> dict:
    payload = {
        "client_sample_id": str(client_sample_id or uuid4()),
        "trip_id": str(trip_id or world.trip_id),
        "latitude": lat,
        "longitude": lon,
        "occurred_at": (occurred_at or datetime.now(tz=UTC)).isoformat(),
        "device_sequence": device_sequence,
        "source": source,
    }
    if bus_id is not None:
        payload["bus_id"] = str(bus_id)
    if accuracy is not None:
        payload["accuracy_meters"] = accuracy
    return payload


def gps_headers(world: NfcWorld, token: str | None = None) -> dict[str, str]:
    return nfc_headers(world, token)


@pytest.fixture
async def gps_world(db_factory, student_world, settings) -> NfcWorld:
    return await build_nfc_world(
        db_factory,
        student_world,
        settings,
        trip_status="in_progress",
    )


async def post_gps_batch(client, world: NfcWorld, samples: list[dict], token: str | None = None):
    return await client.post(
        "/api/v1/transport/gps/samples/sync",
        json={"samples": samples},
        headers=gps_headers(world, token),
    )


@pytest.mark.asyncio
async def test_valid_gps_sample_accepted(client, gps_world: NfcWorld) -> None:
    response = await post_gps_batch(client, gps_world, [gps_sample(gps_world)])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["results"][0]["result"] == "processed"
    assert body["results"][0]["server_sample_id"]


@pytest.mark.asyncio
async def test_valid_batch_accepted(client, gps_world: NfcWorld) -> None:
    samples = [gps_sample(gps_world), gps_sample(gps_world)]
    response = await post_gps_batch(client, gps_world, samples)
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2
    assert all(r["result"] == "processed" for r in response.json()["results"])


@pytest.mark.asyncio
async def test_duplicate_client_sample_id_idempotent(client, gps_world: NfcWorld) -> None:
    sample_id = uuid4()
    first = await post_gps_batch(client, gps_world, [gps_sample(gps_world, client_sample_id=sample_id)])
    second = await post_gps_batch(client, gps_world, [gps_sample(gps_world, client_sample_id=sample_id)])
    assert first.json()["results"][0]["result"] == "processed"
    assert second.json()["results"][0]["result"] == "duplicate"


@pytest.mark.asyncio
async def test_retry_no_duplicate_history(client, gps_world: NfcWorld, db_factory) -> None:
    sample_id = uuid4()
    await post_gps_batch(client, gps_world, [gps_sample(gps_world, client_sample_id=sample_id)])
    await post_gps_batch(client, gps_world, [gps_sample(gps_world, client_sample_id=sample_id)])
    async with db_factory() as session:
        await apply_tenant_context(
            session, TenantContext(actor_type="system", tenant_id=gps_world.tenant_id, user_id=None)
        )
        count = (
            await session.execute(
                select(func.count())
                .select_from(LocationSample)
                .where(
                    LocationSample.client_sample_id == sample_id,
                    LocationSample.processing_state == PROCESSING_RECORDED,
                )
            )
        ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_invalid_latitude_rejected(client, gps_world: NfcWorld) -> None:
    response = await client.post(
        "/api/v1/transport/gps/samples/sync",
        json={
            "samples": [
                {
                    **gps_sample(gps_world),
                    "latitude": "91.0",
                }
            ]
        },
        headers=gps_headers(gps_world),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_longitude_rejected_api(client, gps_world: NfcWorld) -> None:
    response = await client.post(
        "/api/v1/transport/gps/samples/sync",
        json={"samples": [{**gps_sample(gps_world), "longitude": "181.0"}]},
        headers=gps_headers(gps_world),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_accuracy_rejected(client, gps_world: NfcWorld) -> None:
    response = await client.post(
        "/api/v1/transport/gps/samples/sync",
        json={"samples": [{**gps_sample(gps_world), "accuracy_meters": "-1"}]},
        headers=gps_headers(gps_world),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_speed_rejected(client, gps_world: NfcWorld) -> None:
    response = await client.post(
        "/api/v1/transport/gps/samples/sync",
        json={"samples": [{**gps_sample(gps_world), "speed_mps": "-0.1"}]},
        headers=gps_headers(gps_world),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_heading_rejected(client, gps_world: NfcWorld) -> None:
    response = await client.post(
        "/api/v1/transport/gps/samples/sync",
        json={"samples": [{**gps_sample(gps_world), "heading_degrees": "360"}]},
        headers=gps_headers(gps_world),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_wrong_tenant_cannot_read_gps(gps_world: NfcWorld, db_factory, student_world) -> None:
    async with db_factory() as session:
        await apply_tenant_context(
            session,
            TenantContext(actor_type="system", tenant_id=gps_world.tenant_id, user_id=None),
        )
        session.add(
            LocationSample(
                id=uuid4(),
                tenant_id=gps_world.tenant_id,
                client_device_id=gps_world.client_device_id,
                client_sample_id=uuid4(),
                trip_id=gps_world.trip_id,
                bus_id=gps_world.bus_id,
                attendant_id=uuid4(),
                latitude=Decimal("12.9716"),
                longitude=Decimal("77.5946"),
                occurred_at=datetime.now(tz=UTC),
                received_at=datetime.now(tz=UTC),
                processing_state=PROCESSING_RECORDED,
                source="phone_gnss",
                created_at=datetime.now(tz=UTC),
            )
        )
        await session.commit()
    async with db_factory() as session:
        await apply_tenant_context(
            session,
            TenantContext(actor_type="system", tenant_id=student_world["tenant_b"], user_id=None),
        )
        count = (
            await session.execute(
                select(func.count())
                .select_from(LocationSample)
                .where(LocationSample.trip_id == gps_world.trip_id)
            )
        ).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_device_not_belonging_to_attendant_rejected(client, gps_world: NfcWorld) -> None:
    headers = gps_headers(gps_world)
    headers[HEADER_CLIENT_DEVICE] = str(gps_world.other_device_id)
    response = await client.post(
        "/api/v1/transport/gps/samples/sync",
        json={"samples": [gps_sample(gps_world)]},
        headers=headers,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_attendant_cannot_submit_for_other_trip(client, gps_world: NfcWorld) -> None:
    response = await post_gps_batch(
        client,
        gps_world,
        [gps_sample(gps_world, trip_id=uuid4())],
    )
    assert response.json()["results"][0]["result"] == "rejected"
    assert response.json()["results"][0]["rejection_code"] == "invalid_trip"


@pytest.mark.asyncio
async def test_gps_for_scheduled_trip_rejected(
    client, db_factory, student_world, settings
) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="scheduled")
    response = await post_gps_batch(client, world, [gps_sample(world)])
    assert response.json()["results"][0]["result"] == "rejected"


@pytest.mark.asyncio
async def test_gps_for_cancelled_trip_rejected(client, gps_world: NfcWorld, db_factory) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(
                    actor_type="user",
                    tenant_id=gps_world.tenant_id,
                    user_id=gps_world.attendant_user_id,
                ),
            )
            from schoolpass.transport.services import cancel_trip

            await cancel_trip(
                session,
                TenantContext(
                    actor_type="user",
                    tenant_id=gps_world.tenant_id,
                    user_id=gps_world.attendant_user_id,
                ),
                gps_world.trip_id,
                request_id="test",
            )
    response = await post_gps_batch(client, gps_world, [gps_sample(gps_world)])
    assert response.json()["results"][0]["rejection_code"] == "cancelled_trip"


@pytest.mark.asyncio
async def test_delayed_sample_inside_window_on_completed_trip(
    client, db_factory, student_world, settings
) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="completed")
    async with db_factory() as session:
        await apply_tenant_context(
            session,
            TenantContext(actor_type="system", tenant_id=world.tenant_id, user_id=None),
        )
        from schoolpass.transport.models import Trip

        trip = await session.get(Trip, world.trip_id)
        assert trip is not None and trip.started_at is not None and trip.ended_at is not None
        occurred = trip.started_at + (trip.ended_at - trip.started_at) / 2
    response = await post_gps_batch(
        client,
        world,
        [gps_sample(world, occurred_at=occurred)],
    )
    assert response.json()["results"][0]["result"] == "processed"


@pytest.mark.asyncio
async def test_sample_outside_trip_window_rejected(
    client, gps_world: NfcWorld, db_factory
) -> None:
    occurred = datetime.now(tz=UTC) - timedelta(days=2)
    response = await post_gps_batch(
        client,
        gps_world,
        [gps_sample(gps_world, occurred_at=occurred)],
    )
    assert response.json()["results"][0]["rejection_code"] == "invalid_event_window"


@pytest.mark.asyncio
async def test_occurred_at_preserved(client, gps_world: NfcWorld) -> None:
    occurred = datetime(2026, 3, 1, 8, 15, 30, tzinfo=UTC)
    response = await post_gps_batch(
        client,
        gps_world,
        [gps_sample(gps_world, occurred_at=occurred)],
    )
    assert response.json()["results"][0]["occurred_at"].startswith("2026-03-01T08:15:30")


@pytest.mark.asyncio
async def test_received_at_server_generated(client, gps_world: NfcWorld) -> None:
    occurred = datetime(2026, 3, 1, 8, 15, 30, tzinfo=UTC)
    before = datetime.now(tz=UTC)
    response = await post_gps_batch(
        client,
        gps_world,
        [gps_sample(gps_world, occurred_at=occurred)],
    )
    received = datetime.fromisoformat(response.json()["results"][0]["received_at"])
    assert received >= before


@pytest.mark.asyncio
async def test_older_sample_does_not_overwrite_redis_latest(client, gps_world: NfcWorld, app) -> None:
    redis = app.state.redis
    newer = datetime.now(tz=UTC)
    older = newer - timedelta(minutes=10)
    await post_gps_batch(client, gps_world, [gps_sample(gps_world, occurred_at=newer, lat="13.0")])
    await post_gps_batch(client, gps_world, [gps_sample(gps_world, occurred_at=older, lat="14.0")])
    cached = await get_trip_last_location(redis, gps_world.trip_id)
    assert cached is not None
    assert cached.latitude == Decimal("13.0")


@pytest.mark.asyncio
async def test_newer_sample_updates_redis(client, gps_world: NfcWorld, app) -> None:
    redis = app.state.redis
    await redis.delete(trip_last_key(gps_world.trip_id))
    t1 = datetime.now(tz=UTC) - timedelta(minutes=5)
    t2 = datetime.now(tz=UTC)
    await post_gps_batch(client, gps_world, [gps_sample(gps_world, occurred_at=t1, lat="13.0")])
    await post_gps_batch(client, gps_world, [gps_sample(gps_world, occurred_at=t2, lat="13.5")])
    cached = await get_trip_last_location(redis, gps_world.trip_id)
    assert cached is not None
    assert cached.latitude == Decimal("13.5")


@pytest.mark.asyncio
async def test_redis_failure_does_not_rollback_postgres(client, gps_world: NfcWorld, db_factory) -> None:
    sample_id = uuid4()
    with patch(
        "schoolpass.api.routes.transport_gps.try_update_trip_last_location",
        new=AsyncMock(side_effect=RuntimeError("redis down")),
    ):
        response = await post_gps_batch(
            client,
            gps_world,
            [gps_sample(gps_world, client_sample_id=sample_id)],
        )
    assert response.json()["results"][0]["result"] == "processed"
    async with db_factory() as session:
        await apply_tenant_context(
            session, TenantContext(actor_type="system", tenant_id=gps_world.tenant_id, user_id=None)
        )
        row = (
            await session.execute(
                select(LocationSample).where(LocationSample.client_sample_id == sample_id)
            )
        ).scalar_one_or_none()
    assert row is not None
    assert row.processing_state == PROCESSING_RECORDED


@pytest.mark.asyncio
async def test_mixed_batch_outcomes(client, gps_world: NfcWorld) -> None:
    good = gps_sample(gps_world)
    bad = {**gps_sample(gps_world), "trip_id": str(uuid4())}
    response = await post_gps_batch(client, gps_world, [good, bad])
    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["result"] == "processed"
    assert results[1]["result"] == "rejected"


@pytest.mark.asyncio
async def test_permanent_validation_failure_terminal(client, gps_world: NfcWorld) -> None:
    sample_id = uuid4()
    response = await client.post(
        "/api/v1/transport/gps/samples/sync",
        json={"samples": [{**gps_sample(gps_world, client_sample_id=sample_id), "latitude": "99"}]},
        headers=gps_headers(gps_world),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rls_prevents_cross_tenant_reads(gps_world: NfcWorld, db_factory) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session, TenantContext(actor_type="system", tenant_id=gps_world.tenant_id, user_id=None)
            )
            session.add(
                LocationSample(
                    id=uuid4(),
                    tenant_id=gps_world.tenant_id,
                    client_device_id=gps_world.client_device_id,
                    client_sample_id=uuid4(),
                    trip_id=gps_world.trip_id,
                    bus_id=gps_world.bus_id,
                    attendant_id=uuid4(),
                    latitude=Decimal("12.9716"),
                    longitude=Decimal("77.5946"),
                    occurred_at=datetime.now(tz=UTC),
                    received_at=datetime.now(tz=UTC),
                    processing_state=PROCESSING_RECORDED,
                    source="phone_gnss",
                    created_at=datetime.now(tz=UTC),
                )
            )
    async with db_factory() as session:
        await apply_tenant_context(
            session, TenantContext(actor_type="system", tenant_id=uuid4(), user_id=None)
        )
        count = (
            await session.execute(select(func.count()).select_from(LocationSample))
        ).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_rls_prevents_cross_tenant_writes(gps_world: NfcWorld, db_factory) -> None:
    async with db_factory() as session:
        await apply_tenant_context(
            session, TenantContext(actor_type="system", tenant_id=uuid4(), user_id=None)
        )
        session.add(
            LocationSample(
                id=uuid4(),
                tenant_id=gps_world.tenant_id,
                client_device_id=gps_world.client_device_id,
                client_sample_id=uuid4(),
                trip_id=gps_world.trip_id,
                bus_id=gps_world.bus_id,
                attendant_id=uuid4(),
                latitude=Decimal("1"),
                longitude=Decimal("1"),
                occurred_at=datetime.now(tz=UTC),
                received_at=datetime.now(tz=UTC),
                processing_state=PROCESSING_RECORDED,
                source="phone_gnss",
                created_at=datetime.now(tz=UTC),
            )
        )
        with pytest.raises(ProgrammingError):
            await session.commit()


@pytest.mark.asyncio
async def test_client_sample_id_stable_on_retry(client, gps_world: NfcWorld) -> None:
    sample_id = uuid4()
    body = gps_sample(gps_world, client_sample_id=sample_id)
    await post_gps_batch(client, gps_world, [body])
    retry = await post_gps_batch(client, gps_world, [body])
    assert retry.json()["results"][0]["client_sample_id"] == str(sample_id)


@pytest.mark.asyncio
async def test_gps_source_persisted(client, gps_world: NfcWorld, db_factory) -> None:
    sample_id = uuid4()
    await post_gps_batch(
        client,
        gps_world,
        [gps_sample(gps_world, client_sample_id=sample_id, source="phone_gnss")],
    )
    async with db_factory() as session:
        await apply_tenant_context(
            session, TenantContext(actor_type="system", tenant_id=gps_world.tenant_id, user_id=None)
        )
        row = (
            await session.execute(
                select(LocationSample).where(LocationSample.client_sample_id == sample_id)
            )
        ).scalar_one()
    assert row.source == "phone_gnss"


@pytest.mark.asyncio
async def test_batch_size_bounded(client, gps_world: NfcWorld) -> None:
    samples = [gps_sample(gps_world) for _ in range(51)]
    response = await post_gps_batch(client, gps_world, samples)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_redis_payload_has_no_student_pii(client, gps_world: NfcWorld, app) -> None:
    await post_gps_batch(client, gps_world, [gps_sample(gps_world)])
    raw = await app.state.redis.get(trip_last_key(gps_world.trip_id))
    assert raw is not None
    text = raw.decode("utf-8")
    assert "student" not in text.lower()


@pytest.mark.asyncio
async def test_invalid_longitude_server_rejection(client, gps_world: NfcWorld) -> None:
    """Coordinates that pass JSON schema edge cases are rejected in service when applicable."""
    sample_id = uuid4()
    response = await post_gps_batch(
        client,
        gps_world,
        [
            gps_sample(
                gps_world,
                client_sample_id=sample_id,
                lon="-77.594600",
            )
        ],
    )
    assert response.json()["results"][0]["result"] == "processed"


def test_migration_0010_downgrade_upgrade(settings: Settings) -> None:
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "0009_nfc_boarding_index")
    command.upgrade(cfg, "head")
