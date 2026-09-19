"""Teacher notification inbox."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.db.mixins import utcnow
from schoolpass.errors import NotFoundError
from schoolpass.notifications.models import Notification
from schoolpass.teacher.access import load_teacher_staff
from schoolpass.tenancy.context import TenantContext

MAX_PAGE = 100


@dataclass(frozen=True)
class TeacherNotificationRow:
    id: UUID
    notification_type: str
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime


async def list_teacher_notifications(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    limit: int = 50,
) -> list[TeacherNotificationRow]:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    await load_teacher_staff(session, tenant_id=ctx.tenant_id, user_id=ctx.user_id)
    if limit < 1 or limit > MAX_PAGE:
        limit = min(max(limit, 1), MAX_PAGE)
    result = await session.execute(
        select(Notification)
        .where(
            Notification.tenant_id == ctx.tenant_id,
            Notification.recipient_user_id == ctx.user_id,
        )
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return [
        TeacherNotificationRow(
            id=row.id,
            notification_type=row.notification_type,
            title=row.title,
            body=row.body,
            read_at=row.read_at,
            created_at=row.created_at,
        )
        for row in result.scalars()
    ]


async def mark_teacher_notification_read(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    notification_id: UUID,
) -> TeacherNotificationRow:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    await load_teacher_staff(session, tenant_id=ctx.tenant_id, user_id=ctx.user_id)
    row = await session.get(Notification, notification_id)
    if (
        row is None
        or row.tenant_id != ctx.tenant_id
        or row.recipient_user_id != ctx.user_id
    ):
        raise NotFoundError()
    if row.read_at is None:
        row.read_at = utcnow()
        await session.flush()
    return TeacherNotificationRow(
        id=row.id,
        notification_type=row.notification_type,
        title=row.title,
        body=row.body,
        read_at=row.read_at,
        created_at=row.created_at,
    )
