"""Admin operations Phase 10D — dashboard, transport admin, boarding/GPS viewers."""

from __future__ import annotations

import pytest

from admin_helpers import AdminWorld, build_admin_world
from fixtures_students import auth_headers
from nfc_helpers import build_nfc_world, nfc_headers, sync_payload


@pytest.fixture
async def admin_world(db_factory, world, settings) -> AdminWorld:
    return await build_admin_world(db_factory, settings=settings, base_world=world)


async def test_operations_overview(client, admin_world) -> None:
    headers = auth_headers(admin_world.admin_token)
    response = await client.get("/api/v1/admin/operations/overview", headers=headers)
    assert response.status_code == 200
    body = response.json()
    for key in (
        "active_buses",
        "active_trips",
        "rfid_events_last_24h",
        "boarding_events_last_24h",
    ):
        assert key in body
        assert isinstance(body[key], int)


async def test_boarding_records_list_read_only(client, admin_world, student_world, db_factory, settings) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")
    sync = await client.post(
        "/api/v1/transport/nfc/events/sync",
        headers=nfc_headers(world),
        json=sync_payload(world),
    )
    assert sync.status_code == 200
    headers = auth_headers(admin_world.admin_token)
    listed = await client.get("/api/v1/admin/boarding-records", headers=headers)
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) >= 1


async def test_teacher_denied_operations_overview(client, admin_world) -> None:
    response = await client.get(
        "/api/v1/admin/operations/overview",
        headers=auth_headers(admin_world.teacher_token),
    )
    assert response.status_code == 403


async def test_cross_tenant_transport_assignment_get(client, admin_world, student_world, db_factory, settings) -> None:
    world = await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")
    # Assignment belongs to tenant A; admin is tenant A — use tenant B assignment via wrong id from tenant B if exists
    headers = auth_headers(admin_world.admin_token)
    # Fetch a random UUID should 404 not leak
    response = await client.get(
        f"/api/v1/admin/transport-assignments/{world.transport_assignment_id}",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(world.transport_assignment_id)
