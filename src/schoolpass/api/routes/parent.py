from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.adapters.redis import Cache
from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.api.routes.rfid_ingest import get_redis
from schoolpass.db.session import apply_tenant_context
from schoolpass.parent import bus_location as parent_loc
from schoolpass.parent.schemas import ParentBusLocationResponse
from schoolpass.tenancy.context import TenantContext

router = APIRouter(prefix="/api/v1/parent", tags=["parent"])


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


@router.get("/children/{student_id}/bus-location", response_model=ParentBusLocationResponse)
async def get_child_bus_location(
    student_id: UUID,
    principal: Annotated[Principal, Depends(require("parent:gps_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    redis: Annotated[Cache, Depends(get_redis)],
    trip_id: Annotated[UUID | None, Query()] = None,
    bus_id: Annotated[UUID | None, Query()] = None,
) -> ParentBusLocationResponse:
    del trip_id, bus_id
    async with factory() as session:
        await apply_tenant_context(session, _ctx(principal))
        result = await parent_loc.get_parent_child_bus_location(
            session,
            _ctx(principal),
            redis,
            student_id=student_id,
        )
    return ParentBusLocationResponse.from_result(result)
