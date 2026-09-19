from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.admin import profile as admin_profile
from schoolpass.admin.schemas import SchoolProfileResponse, SchoolProfileUpdateRequest
from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.db.session import apply_tenant_context
from schoolpass.tenancy.context import TenantContext

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/school", response_model=SchoolProfileResponse)
async def get_school_profile(
    principal: Annotated[Principal, Depends(require("tenant:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> SchoolProfileResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_profile.get_school_profile(session, _ctx(principal))
    return SchoolProfileResponse.from_tenant(row)


@router.patch("/school", response_model=SchoolProfileResponse)
async def patch_school_profile(
    request: Request,
    body: SchoolProfileUpdateRequest,
    principal: Annotated[Principal, Depends(require("tenant:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> SchoolProfileResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_profile.update_school_profile(
                session,
                _ctx(principal),
                body,
                request_id=_request_id(request),
            )
    return SchoolProfileResponse.from_tenant(row)
