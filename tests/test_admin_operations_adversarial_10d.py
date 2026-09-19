"""Adversarial admin operations/import tests — Phase 10D."""

from __future__ import annotations

import pytest

from admin_helpers import AdminWorld, build_admin_world
from fixtures_students import auth_headers


@pytest.fixture
async def admin_world(db_factory, world, settings) -> AdminWorld:
    return await build_admin_world(db_factory, settings=settings, base_world=world)


async def test_import_unknown_column_rejected(client, admin_world) -> None:
    headers = auth_headers(admin_world.admin_token)
    csv_body = "admission_no,first_name,last_name,evil_column\nA1,Ada,Lovelace,x\n"
    response = await client.post(
        "/api/v1/admin/imports/students/validate",
        headers=headers,
        files={"file": ("import.csv", csv_body.encode(), "text/csv")},
    )
    assert response.status_code in {400, 422}
    assert "unknown" in response.text.lower() or "evil_column" in response.text.lower()


async def test_transport_assignment_create_rejects_foreign_student(
    client, admin_world, student_world, db_factory, settings
) -> None:
    from nfc_helpers import build_nfc_world

    world = await build_nfc_world(db_factory, student_world, settings, trip_status="boarding")
    headers = auth_headers(admin_world.admin_token)
    # Tenant B student id from fixture
    foreign_student = student_world.get("b_student_id")
    if foreign_student is None:
        pytest.skip("fixture missing b_student_id")
    response = await client.post(
        "/api/v1/admin/transport-assignments",
        headers=headers,
        json={
            "student_id": str(foreign_student),
            "route_id": str(world.route_id),
            "stop_id": str(world.route_stop_id),
            "effective_from": "2026-01-01",
        },
    )
    assert response.status_code in {404, 422, 400}
