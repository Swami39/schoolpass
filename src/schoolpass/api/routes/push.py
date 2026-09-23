"""Push device-token registration for all mobile roles.

Complements the role-specific ``/api/v1/parent/push-devices`` route with a
single endpoint every app role (parent, teacher, bus attendant, school
admin) can use. All access is tenant-scoped: tokens are always read and
written for the caller's own tenant and user only.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.api.deps import Principal, get_principal, get_session_factory
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import AuthorizationError
from schoolpass.notifications.devices import (
    register_fcm_device,
    unregister_fcm_device_by_token,
)
from schoolpass.notifications.schemas import PushDeviceResponse, RegisterPushDeviceRequest
from schoolpass.rbac.catalog import ROLE_PERMISSIONS

router = APIRouter(prefix="/api/v1/push", tags=["push"])

PUSH_REGISTER_PERMISSIONS = (
    "parent:push_register",
    "teacher:push_register",
    "bus_attendant:push_register",
    "school_admin:push_register",
)


async def _push_principal(
    principal: Annotated[Principal, Depends(get_principal)],
) -> Principal:
    """Allow any role that may register a device for push notifications."""
    allowed: set[str] = set()
    for role in principal.roles:
        allowed.update(ROLE_PERMISSIONS.get(role, ()))
    principal.permissions = allowed
    if not set(PUSH_REGISTER_PERMISSIONS) & allowed:
        raise AuthorizationError()
    if principal.tenant_id is None and not principal.claims.get("plat"):
        raise AuthorizationError("Tenant membership is required")
    return principal


@router.post("/device-tokens", response_model=PushDeviceResponse)
async def register_device_token(
    body: RegisterPushDeviceRequest,
    principal: Annotated[Principal, Depends(_push_principal)],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> PushDeviceResponse:
    ctx = principal.context
    if ctx.tenant_id is None or ctx.user_id is None:
        raise AuthorizationError("Tenant membership is required")
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, ctx)
            try:
                result = await register_fcm_device(
                    session,
                    tenant_id=ctx.tenant_id,
                    user_id=ctx.user_id,
                    platform=body.platform,
                    fcm_token=body.fcm_token,
                    app_label=body.app_label,
                )
            except PermissionError as exc:
                raise AuthorizationError(str(exc)) from exc
    return PushDeviceResponse.from_device(result.device)


@router.delete("/device-tokens")
async def unregister_device_token(
    principal: Annotated[Principal, Depends(_push_principal)],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    fcm_token: str = Query(min_length=8, max_length=512),
) -> dict[str, bool]:
    """Revoke the caller's device row for ``fcm_token`` (used on logout)."""
    ctx = principal.context
    if ctx.tenant_id is None or ctx.user_id is None:
        raise AuthorizationError("Tenant membership is required")
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, ctx)
            revoked = await unregister_fcm_device_by_token(
                session,
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                fcm_token=fcm_token,
            )
    return {"revoked": revoked}
