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
from schoolpass.parent.attendance_read import list_child_attendance_records
from schoolpass.parent.children import list_linked_children
from schoolpass.parent.schemas import (
    ParentAttendanceListResponse,
    ParentAttendanceRecordItem,
    ParentBusLocationResponse,
    ParentChildItem,
    ParentChildrenListResponse,
)
from schoolpass.tenancy.context import TenantContext

router = APIRouter(prefix="/api/v1/parent", tags=["parent"])


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


@router.get("/children", response_model=ParentChildrenListResponse)
async def list_children(
    principal: Annotated[Principal, Depends(require("parent:children_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ParentChildrenListResponse:
    async with factory() as session:
        await apply_tenant_context(session, _ctx(principal))
        rows = await list_linked_children(session, _ctx(principal))
    return ParentChildrenListResponse(items=[ParentChildItem.from_summary(r) for r in rows])


@router.get("/children/{student_id}/attendance", response_model=ParentAttendanceListResponse)
async def get_child_attendance(
    student_id: UUID,
    principal: Annotated[Principal, Depends(require("parent:attendance_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    date: str | None = Query(default=None, alias="date"),
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> ParentAttendanceListResponse:
    from datetime import date as date_cls

    parsed_date = date_cls.fromisoformat(date) if date else None
    parsed_from = date_cls.fromisoformat(from_date) if from_date else None
    parsed_to = date_cls.fromisoformat(to_date) if to_date else None
    async with factory() as session:
        await apply_tenant_context(session, _ctx(principal))
        rows = await list_child_attendance_records(
            session,
            _ctx(principal),
            student_id=student_id,
            on_date=parsed_date,
            from_date=parsed_from,
            to_date=parsed_to,
            limit=limit,
        )
    return ParentAttendanceListResponse(
        items=[ParentAttendanceRecordItem.from_record(r) for r in rows],
    )


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
