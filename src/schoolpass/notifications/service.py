from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.identity.models import OutboxEvent
from schoolpass.notifications.constants import (
    NOTIFICATION_SCHEMA_VERSION,
    NOTIFICATION_TOPIC_DISPATCH,
    OUTBOX_DISPATCH_SCHEMA_VERSION,
)
from schoolpass.notifications.models import Notification
from schoolpass.outbox.service import enqueue_outbox


@dataclass(frozen=True)
class NotificationCreateResult:
    notification: Notification
    outbox: OutboxEvent
    created: bool


def build_idempotency_key(*, notification_type: str, reference_id: UUID, recipient_user_id: UUID) -> str:
    return f"{notification_type}:{reference_id}:{recipient_user_id}"


def build_outbox_idempotency_key(notification_idempotency_key: str) -> str:
    return f"dispatch:{notification_idempotency_key}"


async def create_notification_with_outbox(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    recipient_user_id: UUID,
    notification_type: str,
    title: str,
    body: str,
    payload: dict[str, Any],
    idempotency_key: str,
    correlation_id: str | None = None,
    reference_type: str | None = None,
    reference_id: UUID | None = None,
    schema_version: int = NOTIFICATION_SCHEMA_VERSION,
) -> NotificationCreateResult:
    """Persist notification inbox row and matching outbox command in the same transaction."""
    notification = Notification(
        tenant_id=tenant_id,
        recipient_user_id=recipient_user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        payload=payload,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        schema_version=schema_version,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    try:
        async with session.begin_nested():
            session.add(notification)
            await session.flush()
    except IntegrityError:
        existing = (
            await session.execute(
                select(Notification).where(
                    Notification.tenant_id == tenant_id,
                    Notification.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one()
        outbox = (
            await session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.topic == NOTIFICATION_TOPIC_DISPATCH,
                    OutboxEvent.idempotency_key == build_outbox_idempotency_key(idempotency_key),
                )
            )
        ).scalar_one()
        return NotificationCreateResult(notification=existing, outbox=outbox, created=False)

    outbox = await enqueue_outbox(
        session,
        topic=NOTIFICATION_TOPIC_DISPATCH,
        idempotency_key=build_outbox_idempotency_key(idempotency_key),
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        schema_version=OUTBOX_DISPATCH_SCHEMA_VERSION,
        payload={
            "notification_id": str(notification.id),
            "notification_type": notification_type,
            "recipient_user_id": str(recipient_user_id),
            "idempotency_key": idempotency_key,
        },
    )
    return NotificationCreateResult(notification=notification, outbox=outbox, created=True)
