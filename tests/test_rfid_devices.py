from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from fixtures_students import auth_headers


@pytest.mark.asyncio
async def test_device_registration_requires_reader(admin_client: AsyncClient, student_world: dict) -> None:
    headers = auth_headers(student_world["token_a"])
    resp = await admin_client.post(
        "/api/v1/rfid-devices",
        headers=headers,
        json={"device_id": f"missing-reader-{uuid4().hex[:6]}", "reader_id": str(uuid4())},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rotate_key_increments_version(admin_client: AsyncClient, student_world: dict) -> None:
    headers = auth_headers(student_world["token_a"])
    reader = await admin_client.post("/api/v1/rfid-readers", headers=headers, json={"name": "Rotate Gate"})
    device = await admin_client.post(
        "/api/v1/rfid-devices",
        headers=headers,
        json={"device_id": f"rotate-{uuid4().hex[:6]}", "reader_id": reader.json()["id"]},
    )
    device_uuid = device.json()["id"]
    rotated = await admin_client.post(f"/api/v1/rfid-devices/{device_uuid}/keys/rotate", headers=headers)
    assert rotated.status_code == 200
    assert rotated.json()["key_version"] == 2
    assert rotated.json()["signing_secret"]
