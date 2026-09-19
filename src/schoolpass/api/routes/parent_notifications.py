from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.db.session import apply_tenant_context
from schoolpass.notifications.devices import register_fcm_device
from schoolpass.notifications.schemas import PushDeviceResponse, RegisterPushDeviceRequest
from schoolpass.parent.notification_preferences_read import (
    list_parent_notification_preferences,
    update_parent_notification_preferences,
)
from schoolpass.parent.notifications_inbox import list_parent_notifications, mark_parent_notification_read
from schoolpass.parent.schemas import (
    ParentNotificationItem,
    ParentNotificationListResponse,
    ParentNotificationPreferenceResponseItem,
    ParentNotificationPreferencesResponse,
    ParentNotificationPreferencesUpdateRequest,
)
from schoolpass.tenancy.context import TenantContext

router = APIRouter(prefix="/api/v1/parent", tags=["parent"])


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


@router.post("/push-devices", response_model=PushDeviceResponse)
async def register_push_device(
    body: RegisterPushDeviceRequest,
    principal: Annotated[Principal, Depends(require("parent:push_register"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> PushDeviceResponse:
    ctx = _ctx(principal)
    if ctx.tenant_id is None or ctx.user_id is None:
        raise RuntimeError("tenant context required")
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, ctx)
            result = await register_fcm_device(
                session,
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                platform=body.platform,
                fcm_token=body.fcm_token,
            )
    return PushDeviceResponse.from_device(result.device)


@router.get("/notifications", response_model=ParentNotificationListResponse)
async def list_notifications(
    principal: Annotated[Principal, Depends(require("parent:notifications_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    limit: int = Query(default=50, ge=1, le=100),
) -> ParentNotificationListResponse:
    ctx = _ctx(principal)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, ctx)
            rows = await list_parent_notifications(session, ctx, limit=limit)
    return ParentNotificationListResponse(items=[ParentNotificationItem.from_row(r) for r in rows])


@router.post("/notifications/{notification_id}/read", response_model=ParentNotificationItem)
async def mark_notification_read(
    notification_id: UUID,
    principal: Annotated[Principal, Depends(require("parent:notifications_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ParentNotificationItem:
    ctx = _ctx(principal)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, ctx)
            row = await mark_parent_notification_read(session, ctx, notification_id=notification_id)
    return ParentNotificationItem.from_row(row)


@router.get("/notification-preferences", response_model=ParentNotificationPreferencesResponse)
async def get_notification_preferences(
    principal: Annotated[Principal, Depends(require("parent:notifications_preferences"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ParentNotificationPreferencesResponse:
    ctx = _ctx(principal)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, ctx)
            rows = await list_parent_notification_preferences(session, ctx)
    return ParentNotificationPreferencesResponse(
        items=[ParentNotificationPreferenceResponseItem.from_item(r) for r in rows],
    )


@router.put("/notification-preferences", response_model=ParentNotificationPreferencesResponse)
async def put_notification_preferences(
    body: ParentNotificationPreferencesUpdateRequest,
    principal: Annotated[Principal, Depends(require("parent:notifications_preferences"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ParentNotificationPreferencesResponse:
    ctx = _ctx(principal)
    updates = [(item.notification_type, item.push_enabled) for item in body.items]
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, ctx)
            rows = await update_parent_notification_preferences(session, ctx, updates=updates)
    return ParentNotificationPreferencesResponse(
        items=[ParentNotificationPreferenceResponseItem.from_item(r) for r in rows],
    )
