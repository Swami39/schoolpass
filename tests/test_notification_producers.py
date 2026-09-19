from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from attendance_helpers import ingest_at, process_attendance_for_tenant, provision_rfid_stack
from notification_helpers import link_guardian_to_parent_user
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import OutboxEvent
from schoolpass.notifications.constants import NOTIFICATION_TOPIC_DISPATCH, NOTIFICATION_TYPE_SCHOOL_ENTRY
from schoolpass.notifications.models import Notification
from schoolpass.tenancy.context import TenantContext


@pytest.mark.asyncio
async def test_school_entry_creates_notification_for_guardian(
    client: AsyncClient,
    student_world: dict,
    db_factory,
    settings,
) -> None:
    parent = await link_guardian_to_parent_user(
        db_factory,
        tenant_id=student_world["tenant_a"],
        guardian_id=student_world["a_guardian_id"],
        student_id=student_world["a_student_id"],
    )
    stack = await provision_rfid_stack(client, student_world)
    await ingest_at(client, stack, occurred_at=datetime(2026, 9, 21, 2, 32, 1, tzinfo=UTC))
    await process_attendance_for_tenant(db_factory, stack["tenant_id"])

    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=stack["tenant_id"], user_id=parent["parent_user_id"]),
            )
            count = (
                await session.execute(
                    select(func.count())
                    .select_from(Notification)
                    .where(
                        Notification.notification_type == NOTIFICATION_TYPE_SCHOOL_ENTRY,
                        Notification.recipient_user_id == parent["parent_user_id"],
                    )
                )
            ).scalar_one()
    assert count == 1
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=stack["tenant_id"], user_id=parent["parent_user_id"]),
            )
            row = (
                await session.execute(
                    select(Notification).where(
                        Notification.recipient_user_id == parent["parent_user_id"]
                    )
                )
            ).scalar_one()
            assert "latitude" not in str(row.payload).lower()
            assert row.payload.get("student_id") == str(student_world["a_student_id"])
            outbox = (
                await session.execute(
                    select(OutboxEvent).where(
                        OutboxEvent.topic == NOTIFICATION_TOPIC_DISPATCH,
                        OutboxEvent.payload["notification_id"].astext == str(row.id),
                    )
                )
            ).scalar_one()
            assert outbox.published_at is None


@pytest.mark.asyncio
async def test_rejected_rfid_no_notification(client: AsyncClient, student_world: dict, db_factory) -> None:
    stack = await provision_rfid_stack(client, student_world)
    payload = {
        "device_event_id": f"evt-{uuid4().hex[:10]}",
        "occurred_at": "2026-09-19T03:00:00+00:00",
        "uhf_epc": "E200UNKNOWN0001",
        "hf_uid": f"HF-{uuid4().hex[:8]}",
    }
    from rfid_helpers import event_body, sign_rfid_ingest

    raw = event_body(**payload)
    headers = sign_rfid_ingest(
        secret=stack["secret"],
        device_id=stack["device_external"],
        key_version=stack["key_version"],
        body=raw,
    )
    resp = await client.post("/ingest/v1/rfid/events", headers=headers, content=raw)
    assert resp.status_code == 200
    await process_attendance_for_tenant(db_factory, stack["tenant_id"])
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=stack["tenant_id"], user_id=student_world["admin_a"]),
            )
            count = (await session.execute(select(func.count()).select_from(Notification))).scalar_one()
    assert count == 0
