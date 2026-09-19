from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.db.session import apply_tenant_context
from schoolpass.notifications.devices import register_fcm_device
from schoolpass.notifications.schemas import PushDeviceResponse, RegisterPushDeviceRequest
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
