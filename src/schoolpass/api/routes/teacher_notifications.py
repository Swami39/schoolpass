from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.db.session import apply_tenant_context
from schoolpass.teacher import notifications_inbox as teacher_notify
from schoolpass.teacher.schemas import TeacherNotificationItem, TeacherNotificationListResponse
from schoolpass.tenancy.context import TenantContext

router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-notifications"])


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


@router.get("/notifications", response_model=TeacherNotificationListResponse)
async def list_notifications(
    principal: Annotated[Principal, Depends(require("teacher:notifications_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    limit: int = Query(default=50, ge=1, le=100),
) -> TeacherNotificationListResponse:
    async with factory() as session:
        await apply_tenant_context(session, _ctx(principal))
        rows = await teacher_notify.list_teacher_notifications(session, _ctx(principal), limit=limit)
    return TeacherNotificationListResponse(items=[TeacherNotificationItem.from_row(r) for r in rows])


@router.post("/notifications/{notification_id}/read", response_model=TeacherNotificationItem)
async def mark_read(
    notification_id: UUID,
    principal: Annotated[Principal, Depends(require("teacher:notifications_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> TeacherNotificationItem:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await teacher_notify.mark_teacher_notification_read(
                session, _ctx(principal), notification_id=notification_id
            )
    return TeacherNotificationItem.from_row(row)
