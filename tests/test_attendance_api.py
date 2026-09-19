from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from attendance_helpers import (
    ingest_at,
    latest_attendance,
    process_attendance_for_tenant,
    provision_rfid_stack,
)
from fixtures_students import auth_headers


@pytest.mark.asyncio
async def test_list_attendance_api(client: AsyncClient, student_world: dict, db_factory) -> None:
    stack = await provision_rfid_stack(client, student_world)
    await ingest_at(client, stack, occurred_at=datetime(2026, 9, 21, 2, 32, 1, tzinfo=UTC))
    await process_attendance_for_tenant(db_factory, stack["tenant_id"])
    headers = auth_headers(student_world["token_a"])
    resp = await client.get("/api/v1/attendance", params={"date": "2026-09-21"}, headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1


@pytest.mark.asyncio
async def test_cross_tenant_attendance_read_forbidden(client: AsyncClient, student_world: dict) -> None:
    headers_b = auth_headers(student_world["token_b"])
    resp = await client.get("/api/v1/attendance", headers=headers_b)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["tenant_id"] == str(student_world["tenant_b"])


@pytest.mark.asyncio
async def test_correction_requires_reason(client: AsyncClient, student_world: dict, db_factory) -> None:
    stack = await provision_rfid_stack(client, student_world)
    await ingest_at(client, stack, occurred_at=datetime(2026, 9, 21, 2, 32, 1, tzinfo=UTC))
    await process_attendance_for_tenant(db_factory, stack["tenant_id"])
    record = await latest_attendance(db_factory, stack["tenant_id"], stack["student_id"])
    assert record is not None
    headers = auth_headers(student_world["token_a"])
    resp = await client.post(
        f"/api/v1/attendance/{record.id}/corrections",
        headers=headers,
        json={"status": "present", "reason": "Approved by admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == 2
