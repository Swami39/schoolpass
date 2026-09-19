"""Parent notification preference reads and updates."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.errors import NotFoundError
from schoolpass.notifications.constants import OPERATIONAL_NOTIFICATION_TYPES
from schoolpass.notifications.preferences import is_push_enabled, set_push_preference
from schoolpass.tenancy.context import TenantContext


@dataclass(frozen=True)
class ParentNotificationPreferenceItem:
    notification_type: str
    push_enabled: bool


async def list_parent_notification_preferences(
    session: AsyncSession,
    ctx: TenantContext,
) -> list[ParentNotificationPreferenceItem]:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    items: list[ParentNotificationPreferenceItem] = []
    for notification_type in sorted(OPERATIONAL_NOTIFICATION_TYPES):
        enabled = await is_push_enabled(
            session,
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            notification_type=notification_type,
        )
        items.append(ParentNotificationPreferenceItem(notification_type=notification_type, push_enabled=enabled))
    return items


async def update_parent_notification_preferences(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    updates: list[tuple[str, bool]],
) -> list[ParentNotificationPreferenceItem]:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    for notification_type, push_enabled in updates:
        if notification_type not in OPERATIONAL_NOTIFICATION_TYPES:
            continue
        await set_push_preference(
            session,
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            notification_type=notification_type,
            push_enabled=push_enabled,
        )
    return await list_parent_notification_preferences(session, ctx)
