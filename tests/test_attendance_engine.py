from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient

from attendance_helpers import (
    ingest_at,
    latest_attendance,
    process_attendance_for_tenant,
    provision_rfid_stack,
)


@pytest.mark.asyncio
async def test_entry_creates_present_record(
    client: AsyncClient,
    student_world: dict,
    db_factory,
) -> None:
    stack = await provision_rfid_stack(client, student_world)
    occurred = datetime(2026, 9, 21, 2, 32, 1, tzinfo=UTC)
    await ingest_at(client, stack, occurred_at=occurred)
    await process_attendance_for_tenant(db_factory, stack["tenant_id"])
    record = await latest_attendance(db_factory, stack["tenant_id"], stack["student_id"])
    assert record is not None
    assert record.status == "present"
    assert record.entry_at == occurred


@pytest.mark.asyncio
async def test_late_entry_status(client: AsyncClient, student_world: dict, db_factory) -> None:
    stack = await provision_rfid_stack(client, student_world)
    occurred = datetime(2026, 9, 21, 3, 7, 0, tzinfo=UTC)
    await ingest_at(client, stack, occurred_at=occurred)
    await process_attendance_for_tenant(db_factory, stack["tenant_id"])
    record = await latest_attendance(db_factory, stack["tenant_id"], stack["student_id"])
    assert record is not None
    assert record.status == "late"


@pytest.mark.asyncio
async def test_repeated_reads_debounced(client: AsyncClient, student_world: dict, db_factory) -> None:
    stack = await provision_rfid_stack(client, student_world)
    base = datetime(2026, 9, 21, 2, 32, 1, tzinfo=UTC)
    for offset in (0, 3, 8, 20):
        await ingest_at(
            client,
            stack,
            occurred_at=base + timedelta(seconds=offset),
            device_event_id=f"evt-{uuid4().hex[:8]}",
        )
        await process_attendance_for_tenant(db_factory, stack["tenant_id"])
    record = await latest_attendance(db_factory, stack["tenant_id"], stack["student_id"])
    assert record is not None
    assert record.entry_at == base


@pytest.mark.asyncio
async def test_out_of_order_entry_uses_earliest(
    client: AsyncClient,
    student_world: dict,
    db_factory,
) -> None:
    stack = await provision_rfid_stack(client, student_world)
    later = datetime(2026, 9, 21, 2, 45, 0, tzinfo=UTC)
    earlier = datetime(2026, 9, 21, 2, 33, 0, tzinfo=UTC)
    await ingest_at(client, stack, occurred_at=later, device_event_id="evt-later")
    await process_attendance_for_tenant(db_factory, stack["tenant_id"])
    await ingest_at(client, stack, occurred_at=earlier, device_event_id="evt-earlier")
    await process_attendance_for_tenant(db_factory, stack["tenant_id"])
    record = await latest_attendance(db_factory, stack["tenant_id"], stack["student_id"])
    assert record is not None
    assert record.entry_at == earlier


@pytest.mark.asyncio
async def test_unknown_card_no_attendance(client: AsyncClient, student_world: dict, db_factory) -> None:
    stack = await provision_rfid_stack(client, student_world)
    from rfid_helpers import event_body, sign_rfid_ingest

    occurred = datetime(2026, 9, 21, 2, 32, 1, tzinfo=UTC)
    raw = event_body(
        device_event_id=f"unknown-{uuid4().hex[:6]}",
        occurred_at=occurred.isoformat(),
        uhf_epc="E200UNKNOWN9999",
    )
    headers = sign_rfid_ingest(
        secret=stack["secret"],
        device_id=stack["device_external"],
        key_version=stack["key_version"],
        body=raw,
    )
    resp = await client.post("/ingest/v1/rfid/events", headers=headers, content=raw)
    assert resp.status_code == 200
    await process_attendance_for_tenant(db_factory, stack["tenant_id"])
    record = await latest_attendance(db_factory, stack["tenant_id"], stack["student_id"])
    assert record is None


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, student_world: dict, db_factory) -> None:
    stack_a = await provision_rfid_stack(client, student_world)
    occurred = datetime(2026, 9, 21, 2, 32, 1, tzinfo=UTC)
    await ingest_at(client, stack_a, occurred_at=occurred)
    await process_attendance_for_tenant(db_factory, stack_a["tenant_id"])
    record_b = await latest_attendance(db_factory, student_world["tenant_b"], student_world["a_student_id"])
    assert record_b is None
