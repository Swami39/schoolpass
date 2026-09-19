from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.attendance import schemas as s
from schoolpass.attendance import services as svc
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import ValidationFailed
from schoolpass.people.pagination import decode_cursor
from schoolpass.tenancy.context import TenantContext

router = APIRouter(prefix="/api/v1", tags=["attendance"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


@router.post("/attendance-policies", response_model=s.AttendancePolicyResponse)
async def create_policy(
    body: s.AttendancePolicyCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("attendance:manage_policy"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AttendancePolicyResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.create_policy(
                session,
                _ctx(principal),
                name=body.name,
                effective_from=body.effective_from,
                effective_to=body.effective_to,
                entry_start_time=body.entry_start_time,
                present_until=body.present_until,
                late_until=body.late_until,
                entry_dedupe_seconds=body.entry_dedupe_seconds,
                exit_dedupe_seconds=body.exit_dedupe_seconds,
                request_id=_request_id(request),
            )
    return s.AttendancePolicyResponse.model_validate(row, from_attributes=True)


@router.get("/attendance-policies", response_model=s.AttendancePolicyListResponse)
async def list_policies(
    principal: Annotated[Principal, Depends(require("attendance:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AttendancePolicyListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await svc.list_policies(session, _ctx(principal))
    return s.AttendancePolicyListResponse(
        items=[s.AttendancePolicyResponse.model_validate(r, from_attributes=True) for r in rows]
    )


@router.patch("/attendance-policies/{policy_id}", response_model=s.AttendancePolicyResponse)
async def patch_policy(
    policy_id: UUID,
    body: s.AttendancePolicyUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require("attendance:manage_policy"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AttendancePolicyResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.patch_policy(
                session,
                _ctx(principal),
                policy_id,
                name=body.name,
                effective_to=body.effective_to,
                entry_start_time=body.entry_start_time,
                present_until=body.present_until,
                late_until=body.late_until,
                entry_dedupe_seconds=body.entry_dedupe_seconds,
                exit_dedupe_seconds=body.exit_dedupe_seconds,
                request_id=_request_id(request),
            )
    return s.AttendancePolicyResponse.model_validate(row, from_attributes=True)


@router.get("/attendance", response_model=s.AttendanceListResponse)
async def list_attendance(
    principal: Annotated[Principal, Depends(require("attendance:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    date: str | None = Query(default=None, alias="date"),
    from_date: str | None = None,
    to_date: str | None = None,
    student_id: UUID | None = None,
    section_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> s.AttendanceListResponse:
    if cursor:
        try:
            decode_cursor(cursor)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc
    from datetime import date as date_cls

    parsed_date = date_cls.fromisoformat(date) if date else None
    parsed_from = date_cls.fromisoformat(from_date) if from_date else None
    parsed_to = date_cls.fromisoformat(to_date) if to_date else None
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await svc.list_records(
                session,
                _ctx(principal),
                on_date=parsed_date,
                from_date=parsed_from,
                to_date=parsed_to,
                student_id=student_id,
                section_id=section_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
    return s.AttendanceListResponse(
        items=[s.AttendanceRecordResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.get("/attendance/summary", response_model=s.AttendanceSummaryResponse)
async def attendance_summary(
    principal: Annotated[Principal, Depends(require("attendance:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    date: str = Query(...),
) -> s.AttendanceSummaryResponse:
    from datetime import date as date_cls

    on_date = date_cls.fromisoformat(date)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            counts = await svc.attendance_summary(session, _ctx(principal), on_date=on_date)
    return s.AttendanceSummaryResponse(date=on_date, **counts)


@router.get("/attendance/{record_id}", response_model=s.AttendanceRecordResponse)
async def get_attendance(
    record_id: UUID,
    principal: Annotated[Principal, Depends(require("attendance:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AttendanceRecordResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_record(session, _ctx(principal), record_id)
    return s.AttendanceRecordResponse.model_validate(row, from_attributes=True)


@router.post("/attendance/{record_id}/corrections", response_model=s.AttendanceRecordResponse)
async def correct_attendance(
    record_id: UUID,
    body: s.AttendanceCorrectionCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("attendance:correct"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AttendanceRecordResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.apply_correction(
                session,
                _ctx(principal),
                record_id,
                new_status=body.status,
                new_entry_at=body.entry_at,
                new_exit_at=body.exit_at,
                reason=body.reason,
                request_id=_request_id(request),
            )
    return s.AttendanceRecordResponse.model_validate(row, from_attributes=True)


@router.post("/attendance/finalize", response_model=s.AttendanceFinalizeResponse)
async def finalize_attendance(
    body: s.AttendanceFinalizeRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require("attendance:finalize"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AttendanceFinalizeResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            run = await svc.finalize_attendance_for_date(
                session,
                _ctx(principal),
                attendance_date=body.date,
                request_id=_request_id(request),
            )
    return s.AttendanceFinalizeResponse(
        attendance_date=run.attendance_date,
        status=run.status,
        run_id=run.id,
    )
