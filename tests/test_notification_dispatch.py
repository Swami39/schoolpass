from __future__ import annotations

from uuid import uuid4

import pytest

from schoolpass.db.session import apply_tenant_context
from schoolpass.notifications.constants import (
    DELIVERY_STATUS_SENT,
    NOTIFICATION_TYPE_SCHOOL_ENTRY,
)
from schoolpass.notifications.delivery import NotificationDeliveryService
from schoolpass.notifications.devices import register_fcm_device
from schoolpass.notifications.dispatch_worker import process_notification_dispatch_message
from schoolpass.notifications.fcm import FcmHttpV1Provider, MemoryFcmCredentials, RecordingFcmTransport
from schoolpass.notifications.models import Notification
from schoolpass.notifications.service import build_idempotency_key, create_notification_with_outbox
from schoolpass.tenancy.context import TenantContext
from schoolpass.worker.main import process_notification_dispatch_batch, publish_outbox_batch


@pytest.mark.asyncio
async def test_outbox_publish_and_worker_delivers(db_factory, student_world, settings) -> None:
    tenant_id = student_world["tenant_a"]
    recipient = student_world["user_a"]
    ref = uuid4()
    idem = build_idempotency_key(
        notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
        reference_id=ref,
        recipient_user_id=recipient,
    )
    notification_id = None
    outbox_id = None
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
            notification_id = result.notification.id
            outbox_id = result.outbox.id
            await register_fcm_device(
                session,
                tenant_id=tenant_id,
                user_id=recipient,
                platform="android",
                fcm_token=f"token-{uuid4().hex}",
            )

    from schoolpass.identity.models import OutboxEvent

    for _ in range(50):
        await publish_outbox_batch()
        async with db_factory() as session:
            async with session.begin():
                await apply_tenant_context(
                    session,
                    TenantContext(actor_type="system", tenant_id=None, user_id=None),
                )
                row = await session.get(OutboxEvent, outbox_id)
                assert row is not None
                if row.published_at is not None:
                    break

    for _ in range(10):
        processed = await process_notification_dispatch_batch()
        if processed:
            break

    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=tenant_id, user_id=recipient),
            )
            row = await session.get(Notification, notification_id)
            assert row is not None
            assert row.delivery_status == DELIVERY_STATUS_SENT


@pytest.mark.asyncio
async def test_malformed_bus_message_rejected(db_factory) -> None:
    transport = RecordingFcmTransport()
    delivery = NotificationDeliveryService(
        fcm=FcmHttpV1Provider(
            project_id="test",
            credentials=MemoryFcmCredentials(),
            transport=transport,
        )
    )
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="system", tenant_id=None, user_id=None))
            outcome = await process_notification_dispatch_message(session, message={"bad": True}, delivery=delivery)
    assert outcome.status == "rejected_malformed"
    assert transport.calls == []
