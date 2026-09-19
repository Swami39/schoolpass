from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from attendance_helpers import ingest_at, process_attendance_for_tenant, provision_rfid_stack
from schoolpass.attendance.models import AttendanceSignal
from schoolpass.db.session import apply_tenant_context
from schoolpass.tenancy.context import TenantContext


@pytest.mark.asyncio
async def test_concurrent_observation_processing_one_signal(
    client: AsyncClient,
    student_world: dict,
    db_factory,
) -> None:
    stack = await provision_rfid_stack(client, student_world)
    occurred = datetime(2026, 9, 21, 2, 32, 1, tzinfo=UTC)
    await ingest_at(client, stack, occurred_at=occurred, device_event_id="concurrent-obs")

    async def run_worker() -> None:
        await process_attendance_for_tenant(db_factory, stack["tenant_id"])

    await asyncio.gather(run_worker(), run_worker())

    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=stack["tenant_id"], user_id=uuid4()),
            )
            count = await session.execute(select(AttendanceSignal))
            signals = list(count.scalars())
    assert len(signals) == 1
