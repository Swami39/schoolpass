"""Parent bus location authorization tests (Phase 6D.1)."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select

from fixtures_students import auth_headers
from parent_gps_helpers import ParentTransportWorld, build_parent_transport_world, seed_redis_trip_location
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.parent.bus_location import authorized_trip_redis_key
from schoolpass.people.models import Guardian
from schoolpass.tenancy.context import TenantContext
from test_transport_api import _role_token


@pytest.fixture
async def parent_world(db_factory, student_world, settings) -> ParentTransportWorld:
    return await build_parent_transport_world(db_factory, student_world, settings)


async def _get(client, world: ParentTransportWorld, student_id, token: str | None = None, **params):
    return await client.get(
        f"/api/v1/parent/children/{student_id}/bus-location",
        headers=auth_headers(token or world.parent_token),
        params=params,
    )


@pytest.mark.asyncio
async def test_parent_can_access_own_child_location(client, parent_world, app) -> None:
    await seed_redis_trip_location(app, parent_world)
    response = await _get(client, parent_world, parent_world.student_id)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["student_id"] == str(parent_world.student_id)
    assert body["latitude"] is not None


@pytest.mark.asyncio
async def test_parent_cannot_access_other_parents_child(client, parent_world) -> None:
    response = await _get(
        client,
        parent_world,
        parent_world.other_child_id,
        token=parent_world.parent_token,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_parent_cannot_access_other_tenant_student(client, parent_world, settings, db_factory, student_world):
    token_b = await _role_token(db_factory, student_world, settings, "parent")
    response = await client.get(
        f"/api/v1/parent/children/{parent_world.tenant_b_student_id}/bus-location",
        headers=auth_headers(token_b),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_changing_student_id_cannot_bypass(client, parent_world, app) -> None:
    await seed_redis_trip_location(app, parent_world)
    response = await _get(client, parent_world, parent_world.other_child_id)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_changing_trip_id_query_ignored(client, parent_world, app) -> None:
    await seed_redis_trip_location(app, parent_world)
    response = await _get(client, parent_world, parent_world.student_id, trip_id=uuid4())
    assert response.status_code == 200
    assert response.json()["trip_id"] == str(parent_world.trip_id)


@pytest.mark.asyncio
async def test_changing_bus_id_query_ignored(client, parent_world, app) -> None:
    await seed_redis_trip_location(app, parent_world)
    response = await _get(client, parent_world, parent_world.student_id, bus_id=uuid4())
    assert response.status_code == 200
    assert response.json()["bus_id"] == str(parent_world.bus_id)


@pytest.mark.asyncio
async def test_no_guardian_link_returns_not_found(client, db_factory, student_world, settings) -> None:
    world = await build_parent_transport_world(
        db_factory,
        student_world,
        settings,
        link_primary_guardian=False,
    )
    response = await _get(client, world, world.student_id)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_suspended_assignment_no_location(client, db_factory, student_world, settings) -> None:
    world = await build_parent_transport_world(
        db_factory,
        student_world,
        settings,
        assignment_active=False,
    )
    response = await _get(client, world, world.student_id)
    assert response.json()["status"] == "no_assignment"


@pytest.mark.asyncio
async def test_no_active_trip(client, db_factory, student_world, settings, app) -> None:
    world = await build_parent_transport_world(
        db_factory,
        student_world,
        settings,
        trip_status="completed",
    )
    await seed_redis_trip_location(app, world)
    response = await _get(client, world, world.student_id)
    assert response.json()["status"] == "no_active_trip"


@pytest.mark.asyncio
async def test_no_redis_location(client, parent_world) -> None:
    response = await _get(client, parent_world, parent_world.student_id)
    assert response.json()["status"] == "location_unavailable"


@pytest.mark.asyncio
async def test_redis_unavailable_handled(client, parent_world) -> None:
    with patch(
        "schoolpass.parent.bus_location.get_trip_last_location",
        new=AsyncMock(side_effect=RuntimeError("redis down")),
    ):
        response = await _get(client, parent_world, parent_world.student_id)
    assert response.status_code == 200
    assert response.json()["status"] == "cache_unavailable"


@pytest.mark.asyncio
async def test_redis_key_derived_server_side(parent_world) -> None:
    assert authorized_trip_redis_key(parent_world.trip_id) == f"trip:{parent_world.trip_id}:last"


@pytest.mark.asyncio
async def test_completed_trip_not_current(client, db_factory, student_world, settings, app) -> None:
    world = await build_parent_transport_world(db_factory, student_world, settings, trip_status="completed")
    await seed_redis_trip_location(app, world)
    response = await _get(client, world, world.student_id)
    assert response.json()["status"] == "no_active_trip"


@pytest.mark.asyncio
async def test_cancelled_trip_not_current(client, db_factory, student_world, settings, app) -> None:
    world = await build_parent_transport_world(db_factory, student_world, settings, trip_status="cancelled")
    await seed_redis_trip_location(app, world)
    response = await _get(client, world, world.student_id)
    assert response.json()["status"] == "no_active_trip"


@pytest.mark.asyncio
async def test_effective_assignment_date_respected(client, db_factory, student_world, settings) -> None:
    future = date.today() + timedelta(days=30)
    world = await build_parent_transport_world(
        db_factory,
        student_world,
        settings,
        assignment_effective_from=future,
    )
    response = await _get(client, world, world.student_id)
    assert response.json()["status"] == "no_assignment"


@pytest.mark.asyncio
async def test_rls_tenant_isolation(db_factory, parent_world) -> None:
    async with db_factory() as session:
        await apply_tenant_context(
            session,
            TenantContext(actor_type="system", tenant_id=uuid4(), user_id=None),
        )
        count = (await session.execute(select(func.count()).select_from(Guardian))).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_no_gps_history_on_endpoint(client, parent_world, app) -> None:
    await seed_redis_trip_location(app, parent_world)
    response = await _get(client, parent_world, parent_world.student_id)
    body = response.json()
    assert "items" not in body
    assert "history" not in body


@pytest.mark.asyncio
async def test_response_has_no_attendant_fields(client, parent_world, app) -> None:
    await seed_redis_trip_location(app, parent_world)
    body = (await _get(client, parent_world, parent_world.student_id)).json()
    for key in body:
        assert "attendant" not in key
        assert "device" not in key


@pytest.mark.asyncio
async def test_audit_does_not_contain_coordinates(client, parent_world, app) -> None:
    await seed_redis_trip_location(app, parent_world)
    with patch("schoolpass.audit.service.record_audit", new=AsyncMock()) as audit_mock:
        await _get(client, parent_world, parent_world.student_id)
    assert audit_mock.call_count == 0


@pytest.mark.asyncio
async def test_non_parent_cannot_use_endpoint(client, parent_world, db_factory, student_world, settings) -> None:
    token = await _role_token(db_factory, student_world, settings, "teacher")
    response = await client.get(
        f"/api/v1/parent/children/{parent_world.student_id}/bus-location",
        headers=auth_headers(token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_adversarial_parent_other_student_id(client, parent_world, app) -> None:
    await seed_redis_trip_location(app, parent_world)
    response = await _get(client, parent_world, parent_world.other_child_id)
    assert response.status_code == 404


def test_migration_0011_downgrade_upgrade(settings: Settings) -> None:
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "0010_transport_gps")
    command.upgrade(cfg, "head")
