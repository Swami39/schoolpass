from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.identity.models import OutboxEvent


async def enqueue_outbox(
    session: AsyncSession,
    *,
    topic: str,
    idempotency_key: str,
    payload: dict[str, Any],
    tenant_id: UUID | None = None,
    correlation_id: str | None = None,
    schema_version: int = 1,
) -> OutboxEvent:
    event = OutboxEvent(
        tenant_id=tenant_id,
        topic=topic,
        schema_version=schema_version,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        payload=payload,
    )
    session.add(event)
    await session.flush()
    return event
