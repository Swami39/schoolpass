from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.api.deps import Principal, get_principal, get_session_factory, require
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import NotFoundError
from schoolpass.identity.models import StaffProfile, Tenant

router = APIRouter(prefix="/api/v1", tags=["session"])


class MeResponse(BaseModel):
    id: UUID
    email: str | None
    phone_e164: str | None
    roles: list[str]
    tenant_id: UUID | None
    mfa_enabled: bool


class StaffItem(BaseModel):
    id: UUID
    user_id: UUID
    staff_type: str
    employee_code: str | None


class StaffListResponse(BaseModel):
    items: list[StaffItem]
    next_cursor: str | None = None


class TenantItem(BaseModel):
    id: UUID
    legal_name: str
    slug: str
    status: str


@router.get("/auth/me", response_model=MeResponse)
async def me(principal: Annotated[Principal, Depends(get_principal)]) -> MeResponse:
    return MeResponse(
        id=principal.user.id,
        email=principal.user.email,
        phone_e164=principal.user.phone_e164,
        roles=principal.roles,
        tenant_id=principal.tenant_id,
        mfa_enabled=principal.user.mfa_enabled,
    )


@router.get("/staff", response_model=StaffListResponse)
async def list_staff(
    request: Request,
    principal: Annotated[Principal, Depends(require("staff:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> StaffListResponse:
    if principal.tenant_id is None:
        raise NotFoundError()
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, principal.context)
            result = await session.execute(select(StaffProfile))
            rows = result.scalars().all()
    return StaffListResponse(
        items=[
            StaffItem(
                id=row.id,
                user_id=row.user_id,
                staff_type=row.staff_type,
                employee_code=row.employee_code,
            )
            for row in rows
        ]
    )


@router.get("/platform/tenants")
async def list_tenants(
    principal: Annotated[Principal, Depends(require("tenant:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> dict[str, Any]:
    if not principal.claims.get("plat"):
        raise NotFoundError()
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, principal.context)
            result = await session.execute(select(Tenant).order_by(Tenant.slug))
            rows = result.scalars().all()
    return {
        "items": [
            TenantItem(id=row.id, legal_name=row.legal_name, slug=row.slug, status=row.status).model_dump()
            for row in rows
        ],
        "next_cursor": None,
    }
