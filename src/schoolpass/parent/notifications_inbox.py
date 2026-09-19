"""Parent notification inbox reads and read-state updates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.db.mixins import utcnow
from schoolpass.errors import NotFoundError
from schoolpass.notifications.models import Notification
from schoolpass.tenancy.context import TenantContext

MAX_PAGE = 100


@dataclass(frozen=True)
class ParentNotificationRow:
    id: UUID
    notification_type: str
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime
    student_id: UUID | None


async def list_parent_notifications(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    limit: int = 50,
) -> list[ParentNotificationRow]:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
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
    rows: list[ParentNotificationRow] = []
    for row in result.scalars():
        payload = row.payload or {}
        student_raw = payload.get("student_id")
        student_id = UUID(student_raw) if isinstance(student_raw, str) else None
        rows.append(
            ParentNotificationRow(
                id=row.id,
                notification_type=row.notification_type,
                title=row.title,
                body=row.body,
                read_at=row.read_at,
                created_at=row.created_at,
                student_id=student_id,
            )
        )
    return rows


async def mark_parent_notification_read(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    notification_id: UUID,
) -> ParentNotificationRow:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    row = await session.get(Notification, notification_id)
    if (
        row is None
        or row.tenant_id != ctx.tenant_id
        or row.recipient_user_id != ctx.user_id
    ):
        raise NotFoundError()
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        row.updated_at = utcnow()
        await session.flush()
    payload = row.payload or {}
    student_raw = payload.get("student_id")
    student_id = UUID(student_raw) if isinstance(student_raw, str) else None
    return ParentNotificationRow(
        id=row.id,
        notification_type=row.notification_type,
        title=row.title,
        body=row.body,
        read_at=row.read_at,
        created_at=row.created_at,
        student_id=student_id,
    )
