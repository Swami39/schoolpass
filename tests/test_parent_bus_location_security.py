"""Phase 6D.2 adversarial tests for parent bus location API."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from fixtures_students import auth_headers
from parent_gps_helpers import (
    FORBIDDEN_PARENT_LOCATION_RESPONSE_KEYS,
    ParentTransportWorld,
    build_parent_transport_world,
    seed_redis_raw,
    seed_redis_trip_location,
)
from schoolpass.transport.gps_redis import TripLastLocation
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


def _assert_minimal_response(body: dict) -> None:
    assert FORBIDDEN_PARENT_LOCATION_RESPONSE_KEYS.isdisjoint(body.keys())
    serialized = json.dumps(body)
    assert "trip:" not in serialized
    assert ":last" not in serialized
    for key in body:
        assert "attendant" not in key
        assert "device" not in key
        assert "guardian" not in key
        assert "tenant" not in key


@pytest.mark.asyncio
async def test_adversarial_parent_a_requests_parent_b_student(client, parent_world, app) -> None:
    """A: Parent A must not access Parent B's student."""
    await seed_redis_trip_location(app, parent_world)
    response = await _get(client, parent_world, parent_world.other_child_id)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_adversarial_other_student_plus_other_trip_id(client, parent_world, app) -> None:
    """B: Other student_id plus attacker trip_id still 404."""
    await seed_redis_trip_location(app, parent_world)
    response = await _get(
        client,
        parent_world,
        parent_world.other_child_id,
        trip_id=parent_world.trip_id,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_adversarial_own_student_foreign_trip_id_query(client, parent_world, app) -> None:
    """C: Supplied trip_id must not select another trip's Redis location."""
    await seed_redis_trip_location(app, parent_world)
    foreign_trip = uuid4()
    await seed_redis_trip_location(
        app,
        parent_world,
        trip_id=foreign_trip,
        latitude=Decimal("99.000000"),
        longitude=Decimal("88.000000"),
    )
    response = await _get(client, parent_world, parent_world.student_id, trip_id=foreign_trip)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["trip_id"] == str(parent_world.trip_id)
    assert body["latitude"] == "12.971600"
    assert body["latitude"] != "99.000000"


@pytest.mark.asyncio
async def test_adversarial_own_student_foreign_bus_id_query(client, parent_world, app) -> None:
    """D: Supplied bus_id must not change authorized bus."""
    await seed_redis_trip_location(app, parent_world)
    response = await _get(client, parent_world, parent_world.student_id, bus_id=uuid4())
    assert response.status_code == 200
    body = response.json()
    assert body["bus_id"] == str(parent_world.bus_id)


@pytest.mark.asyncio
async def test_redis_payload_trip_id_mismatch(client, parent_world, app) -> None:
    """E: Cached trip_id must match authorized trip."""
    sample = TripLastLocation(
        trip_id=uuid4(),
        bus_id=parent_world.bus_id,
        latitude=Decimal("12.971600"),
        longitude=Decimal("77.594600"),
        occurred_at=datetime.now(tz=UTC),
        accuracy_meters=None,
        received_at=datetime.now(tz=UTC),
    )
    await seed_redis_raw(app, parent_world.trip_id, sample.to_json())
    body = (await _get(client, parent_world, parent_world.student_id)).json()
    assert body["status"] == "location_unavailable"
    assert body.get("latitude") is None


@pytest.mark.asyncio
async def test_redis_payload_bus_id_mismatch(client, parent_world, app) -> None:
    """F: Cached bus_id must match authorized trip bus."""
    sample = TripLastLocation(
        trip_id=parent_world.trip_id,
        bus_id=uuid4(),
        latitude=Decimal("12.971600"),
        longitude=Decimal("77.594600"),
        occurred_at=datetime.now(tz=UTC),
        accuracy_meters=None,
        received_at=datetime.now(tz=UTC),
    )
    await seed_redis_raw(app, parent_world.trip_id, sample.to_json())
    body = (await _get(client, parent_world, parent_world.student_id)).json()
    assert body["status"] == "location_unavailable"
    assert body.get("latitude") is None


@pytest.mark.asyncio
async def test_redis_malformed_payload_safe(client, parent_world, app) -> None:
    """G: Malformed Redis must not 500 or leak internals."""
    await seed_redis_raw(app, parent_world.trip_id, "{not-valid-json")
    response = await _get(client, parent_world, parent_world.student_id)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cache_unavailable"
    assert "redis" not in response.text.lower()
    assert "traceback" not in response.text.lower()


@pytest.mark.asyncio
async def test_inactive_guardian_denied(client, db_factory, student_world, settings) -> None:
    """H: Inactive guardian cannot read location."""
    world = await build_parent_transport_world(
        db_factory,
        student_world,
        settings,
        guardian_status="inactive",
    )
    response = await _get(client, world, world.student_id)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_inactive_student_guardian_link_denied(client, db_factory, student_world, settings) -> None:
    """I: Revoked StudentGuardian link is denied."""
    world = await build_parent_transport_world(
        db_factory,
        student_world,
        settings,
        student_guardian_active=False,
    )
    response = await _get(client, world, world.student_id)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_authorized_parent_no_effective_assignment(client, db_factory, student_world, settings) -> None:
    """J: Linked parent with no effective assignment → no_assignment."""
    world = await build_parent_transport_world(
        db_factory,
        student_world,
        settings,
        assignment_active=False,
    )
    body = (await _get(client, world, world.student_id)).json()
    assert body["status"] == "no_assignment"
    assert body.get("latitude") is None


@pytest.mark.asyncio
async def test_scheduled_trip_only_no_active_trip(client, db_factory, student_world, settings, app) -> None:
    """K: Scheduled trip must not expose live location."""
    world = await build_parent_transport_world(
        db_factory,
        student_world,
        settings,
        trip_status="scheduled",
    )
    await seed_redis_trip_location(app, world)
    body = (await _get(client, world, world.student_id)).json()
    assert body["status"] == "no_active_trip"
    assert body.get("latitude") is None


@pytest.mark.asyncio
async def test_unrelated_in_progress_trip_redis_not_used(client, db_factory, student_world, settings, app) -> None:
    """L: Redis on another active trip must not be returned for this student."""
    world = await build_parent_transport_world(
        db_factory,
        student_world,
        settings,
        trip_status="scheduled",
        decoy_in_progress_trip=True,
    )
    assert world.decoy_trip_id is not None
    await seed_redis_trip_location(
        app,
        world,
        trip_id=world.decoy_trip_id,
        latitude=Decimal("99.111111"),
        longitude=Decimal("88.222222"),
    )
    body = (await _get(client, world, world.student_id)).json()
    assert body["status"] == "no_active_trip"
    assert body.get("latitude") is None


@pytest.mark.asyncio
async def test_teacher_cannot_use_parent_endpoint(client, parent_world, db_factory, student_world, settings) -> None:
    """M: Teacher receives 403."""
    token = await _role_token(db_factory, student_world, settings, "teacher")
    response = await client.get(
        f"/api/v1/parent/children/{parent_world.student_id}/bus-location",
        headers=auth_headers(token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_parent_permission_without_guardian_denied(
    client, parent_world, db_factory, student_world, settings
) -> None:
    """N: parent:gps_read alone is insufficient without guardian linkage."""
    token = await _role_token(db_factory, student_world, settings, "parent")
    response = await client.get(
        f"/api/v1/parent/children/{parent_world.student_id}/bus-location",
        headers=auth_headers(token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_response_excludes_internal_fields(client, parent_world, app) -> None:
    """O: Response must not expose internal identifiers or cache details."""
    await seed_redis_trip_location(app, parent_world)
    body = (await _get(client, parent_world, parent_world.student_id)).json()
    _assert_minimal_response(body)


@pytest.mark.asyncio
async def test_get_does_not_emit_audit(client, parent_world, app) -> None:
    """P: GET must not write audit records."""
    await seed_redis_trip_location(app, parent_world)
    with patch("schoolpass.audit.service.record_audit", new=AsyncMock()) as audit_mock:
        await _get(client, parent_world, parent_world.student_id)
    assert audit_mock.call_count == 0


@pytest.mark.asyncio
async def test_no_coordinates_in_application_logs(client, parent_world, app, caplog) -> None:
    """Q: Successful reads must not log GPS coordinates."""
    await seed_redis_trip_location(app, parent_world)
    caplog.set_level(logging.DEBUG)
    await _get(client, parent_world, parent_world.student_id)
    log_blob = caplog.text.lower()
    assert "12.971600" not in log_blob
    assert "77.594600" not in log_blob
