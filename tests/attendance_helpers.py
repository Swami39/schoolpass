from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fixtures_students import auth_headers
from rfid_helpers import event_body, sign_rfid_ingest
from schoolpass.attendance.engine import process_pending_observations
from schoolpass.attendance.models import AttendanceRecord
from schoolpass.db.session import apply_tenant_context
from schoolpass.tenancy.context import TenantContext


async def ensure_enrollment(
    client: AsyncClient,
    student_world: dict,
) -> None:
    headers = auth_headers(student_world["token_a"])
    existing = await client.get(
        f"/api/v1/students/{student_world['a_student_id']}/enrollments",
        headers=headers,
    )
    if existing.json().get("items"):
        return
    resp = await client.post(
        "/api/v1/enrollments",
        headers=headers,
        json={
            "student_id": str(student_world["a_student_id"]),
            "academic_year_id": str(student_world["a_year_id"]),
            "class_id": str(student_world["a_class_id"]),
            "section_id": str(student_world["a_section_id"]),
            "starts_on": "2025-04-01",
        },
    )
    assert resp.status_code == 200


async def ensure_policy(client: AsyncClient, student_world: dict) -> None:
    headers = auth_headers(student_world["token_a"])
    listed = await client.get("/api/v1/attendance-policies", headers=headers)
    if listed.status_code == 200 and listed.json()["items"]:
        return
    resp = await client.post(
        "/api/v1/attendance-policies",
        headers=headers,
        json={
            "name": "Default",
            "effective_from": "2025-04-01",
            "entry_start_time": "07:00:00",
            "present_until": "08:15:00",
            "late_until": "09:00:00",
            "entry_dedupe_seconds": 30,
            "exit_dedupe_seconds": 30,
        },
    )
    assert resp.status_code == 200


async def provision_rfid_stack(client: AsyncClient, student_world: dict) -> dict:
    await ensure_enrollment(client, student_world)
    await ensure_policy(client, student_world)
    headers = auth_headers(student_world["token_a"])
    card = await client.post(
        "/api/v1/cards",
        json={"hf_uid": f"HF-{uuid4().hex[:8]}", "uhf_epc": f"E200{uuid4().hex[:8].upper()}", "profile": "uid_only"},
        headers=headers,
    )
    card_body = card.json()
    await client.post(f"/api/v1/cards/{card_body['id']}/activate", headers=headers)
    assignment = await client.post(
        "/api/v1/card-assignments",
        json={"student_id": str(student_world["a_student_id"]), "physical_card_id": card_body["id"]},
        headers=headers,
    )
    await client.post(f"/api/v1/card-assignments/{assignment.json()['id']}/activate", headers=headers)
    reader = await client.post(
        "/api/v1/rfid-readers",
        headers=headers,
        json={"name": "Main Gate", "direction_mode": "entry"},
    )
    reader_id = reader.json()["id"]
    device_external = f"dev-{uuid4().hex[:8]}"
    device = await client.post(
        "/api/v1/rfid-devices",
        headers=headers,
        json={"device_id": device_external, "reader_id": reader_id},
    )
    device_body = device.json()
    return {
        "headers": headers,
        "secret": device_body["signing_secret"],
        "device_external": device_external,
        "key_version": device_body["key_version"],
        "card": card_body,
        "student_id": student_world["a_student_id"],
        "tenant_id": student_world["tenant_a"],
    }


async def ingest_at(
    client: AsyncClient,
    stack: dict,
    *,
    occurred_at: datetime,
    device_event_id: str | None = None,
    direction: str | None = None,
) -> None:
    payload = {
        "device_event_id": device_event_id or f"evt-{uuid4().hex[:10]}",
        "occurred_at": occurred_at.isoformat(),
        "uhf_epc": stack["card"]["uhf_epc"],
        "hf_uid": stack["card"]["hf_uid"],
    }
    if direction:
        payload["direction"] = direction
    raw = event_body(**payload)
    headers = sign_rfid_ingest(
        secret=stack["secret"],
        device_id=stack["device_external"],
        key_version=stack["key_version"],
        body=raw,
    )
    resp = await client.post("/ingest/v1/rfid/events", headers=headers, content=raw)
    assert resp.status_code == 200


async def process_attendance_for_tenant(
    db_factory: async_sessionmaker[AsyncSession],
    tenant_id,
) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="worker", tenant_id=tenant_id, user_id=None),
            )
            await process_pending_observations(session)


async def latest_attendance(
    db_factory: async_sessionmaker[AsyncSession],
    tenant_id,
    student_id,
) -> AttendanceRecord | None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=tenant_id, user_id=uuid4()),
            )
            result = await session.execute(
                select(AttendanceRecord)
                .where(
                    AttendanceRecord.tenant_id == tenant_id,
                    AttendanceRecord.student_id == student_id,
                )
                .order_by(AttendanceRecord.attendance_date.desc())
            )
            return result.scalar_one_or_none()
