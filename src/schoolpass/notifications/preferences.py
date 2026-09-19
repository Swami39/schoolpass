from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.notifications.constants import OPERATIONAL_NOTIFICATION_TYPES
from schoolpass.notifications.models import NotificationPreference


async def is_push_enabled(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    notification_type: str,
) -> bool:
    if notification_type not in OPERATIONAL_NOTIFICATION_TYPES:
        return True
    row = (
        await session.execute(
            select(NotificationPreference).where(
                NotificationPreference.tenant_id == tenant_id,
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return True
    return row.push_enabled


async def set_push_preference(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    notification_type: str,
    push_enabled: bool,
) -> NotificationPreference:
    row = (
        await session.execute(
            select(NotificationPreference).where(
                NotificationPreference.tenant_id == tenant_id,
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = NotificationPreference(
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=notification_type,
            push_enabled=push_enabled,
        )
        session.add(row)
    else:
        row.push_enabled = push_enabled
    await session.flush()
    return row
