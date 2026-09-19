"""Parent-safe attendance reads for linked children."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.attendance.models import AttendanceRecord
from schoolpass.errors import NotFoundError
from schoolpass.parent.guardian_access import assert_user_linked_to_student
from schoolpass.tenancy.context import TenantContext

MAX_PAGE = 100


async def list_child_attendance_records(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    student_id: UUID,
    on_date: date | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 50,
) -> list[AttendanceRecord]:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    if limit < 1 or limit > MAX_PAGE:
        limit = min(max(limit, 1), MAX_PAGE)
    await assert_user_linked_to_student(
        session,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        student_id=student_id,
    )
    query = select(AttendanceRecord).where(
        AttendanceRecord.tenant_id == ctx.tenant_id,
        AttendanceRecord.student_id == student_id,
    )
    if on_date is not None:
        query = query.where(AttendanceRecord.attendance_date == on_date)
    if from_date is not None:
        query = query.where(AttendanceRecord.attendance_date >= from_date)
    if to_date is not None:
        query = query.where(AttendanceRecord.attendance_date <= to_date)
    query = query.order_by(AttendanceRecord.attendance_date.desc()).limit(limit)
    result = await session.execute(query)
    return list(result.scalars())
