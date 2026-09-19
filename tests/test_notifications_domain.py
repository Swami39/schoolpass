"""Notification domain and transactional outbox (Phase 7.1)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import OutboxEvent
from schoolpass.notifications.constants import NOTIFICATION_TOPIC_DISPATCH, NOTIFICATION_TYPE_SCHOOL_ENTRY
from schoolpass.notifications.models import Notification
from schoolpass.notifications.service import (
    build_idempotency_key,
    build_outbox_idempotency_key,
    create_notification_with_outbox,
)
from schoolpass.tenancy.context import TenantContext


@pytest.mark.asyncio
async def test_create_notification_with_outbox(db_factory, student_world) -> None:
    tenant_id = student_world["tenant_a"]
    recipient = student_world["user_a"]
    idem = build_idempotency_key(
        notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
        reference_id=uuid4(),
        recipient_user_id=recipient,
    )
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=tenant_id, user_id=recipient),
            )
            result = await create_notification_with_outbox(
                session,
                tenant_id=tenant_id,
                recipient_user_id=recipient,
                notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
                title="School entry",
                body="Your child has entered school.",
                payload={"student_id": str(student_world["a_student_id"]), "reference_type": "attendance_signal"},
                idempotency_key=idem,
                correlation_id="corr-1",
                reference_type="attendance_signal",
                reference_id=uuid4(),
            )
            assert result.created is True
            assert result.notification.schema_version == 1
            assert result.notification.read_at is None
            assert result.outbox.published_at is None
            assert result.outbox.topic == NOTIFICATION_TOPIC_DISPATCH
            assert "latitude" not in str(result.notification.payload)
            assert "password" not in str(result.notification.payload)


@pytest.mark.asyncio
async def test_idempotent_duplicate_returns_existing(db_factory, student_world) -> None:
    tenant_id = student_world["tenant_a"]
    recipient = student_world["user_a"]
    ref = uuid4()
    idem = build_idempotency_key(
        notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
        reference_id=ref,
        recipient_user_id=recipient,
    )
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=tenant_id, user_id=recipient),
            )
            first = await create_notification_with_outbox(
                session,
                tenant_id=tenant_id,
                recipient_user_id=recipient,
                notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
                title="School entry",
                body="Body",
                payload={"student_id": str(student_world["a_student_id"])},
                idempotency_key=idem,
            )
            second = await create_notification_with_outbox(
                session,
                tenant_id=tenant_id,
                recipient_user_id=recipient,
                notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
                title="Different",
                body="Different",
                payload={"student_id": str(student_world["a_student_id"])},
                idempotency_key=idem,
            )
            assert second.created is False
            assert second.notification.id == first.notification.id
            assert second.outbox.id == first.outbox.id


@pytest.mark.asyncio
async def test_concurrent_duplicate_idempotency(db_factory, student_world) -> None:
    tenant_id = student_world["tenant_a"]
    recipient = student_world["user_a"]
    ref = uuid4()
    idem = build_idempotency_key(
        notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
        reference_id=ref,
        recipient_user_id=recipient,
    )

    async def once() -> None:
        async with db_factory() as session:
            async with session.begin():
                await apply_tenant_context(
                    session,
                    TenantContext(actor_type="user", tenant_id=tenant_id, user_id=recipient),
                )
                await create_notification_with_outbox(
                    session,
                    tenant_id=tenant_id,
                    recipient_user_id=recipient,
                    notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
                    title="School entry",
                    body="Body",
                    payload={"student_id": str(student_world["a_student_id"])},
                    idempotency_key=idem,
                )

    await asyncio.gather(*(once() for _ in range(5)))
    async with db_factory() as session:
        await apply_tenant_context(
            session,
            TenantContext(actor_type="user", tenant_id=tenant_id, user_id=recipient),
        )
        count = (
            await session.execute(
                select(func.count()).select_from(Notification).where(Notification.idempotency_key == idem)
            )
        ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_atomic_rollback_no_notification_or_outbox(db_factory, student_world) -> None:
    tenant_id = student_world["tenant_a"]
    recipient = student_world["user_a"]
    idem = f"rollback-test:{uuid4()}"
    try:
        async with db_factory() as session:
            async with session.begin():
                await apply_tenant_context(
                    session,
                    TenantContext(actor_type="user", tenant_id=tenant_id, user_id=recipient),
                )
                await create_notification_with_outbox(
                    session,
                    tenant_id=tenant_id,
                    recipient_user_id=recipient,
                    notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
                    title="School entry",
                    body="Body",
                    payload={"student_id": str(student_world["a_student_id"])},
                    idempotency_key=idem,
                )
                raise RuntimeError("force rollback")
    except RuntimeError:
        pass
    async with db_factory() as session:
        await apply_tenant_context(
            session,
            TenantContext(actor_type="user", tenant_id=tenant_id, user_id=recipient),
        )
        n_count = (
            await session.execute(
                select(func.count()).select_from(Notification).where(Notification.idempotency_key == idem)
            )
        ).scalar_one()
        o_count = (
            await session.execute(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.idempotency_key == build_outbox_idempotency_key(idem))
            )
        ).scalar_one()
    assert n_count == 0
    assert o_count == 0


@pytest.mark.asyncio
async def test_rls_tenant_isolation(db_factory, student_world) -> None:
    async with db_factory() as session:
        await apply_tenant_context(
            session,
            TenantContext(actor_type="system", tenant_id=uuid4(), user_id=None),
        )
        count = (await session.execute(select(func.count()).select_from(Notification))).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_outbox_topic_isolated(db_factory, student_world) -> None:
    tenant_id = student_world["tenant_a"]
    recipient = student_world["user_a"]
    idem = build_idempotency_key(
        notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
        reference_id=uuid4(),
        recipient_user_id=recipient,
    )
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=tenant_id, user_id=recipient),
            )
            result = await create_notification_with_outbox(
                session,
                tenant_id=tenant_id,
                recipient_user_id=recipient,
                notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
                title="School entry",
                body="Body",
                payload={"student_id": str(student_world["a_student_id"])},
                idempotency_key=idem,
            )
            assert result.outbox.topic == NOTIFICATION_TOPIC_DISPATCH
