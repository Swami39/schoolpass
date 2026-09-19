"""Teacher-scoped attendance reads and writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.attendance.models import AttendanceRecord
from schoolpass.attendance.services import apply_correction
from schoolpass.db.mixins import utcnow
from schoolpass.errors import NotFoundError, ValidationFailed
from schoolpass.people.models import Enrollment
from schoolpass.teacher.access import assert_student_in_teacher_section, assert_teacher_assigned_to_section
from schoolpass.tenancy.context import TenantContext

ALLOWED_MARK_STATUSES = frozenset({"present", "late", "absent", "excused"})


@dataclass(frozen=True)
class TeacherAttendanceRow:
    id: UUID
    student_id: UUID
    attendance_date: date
    status: str
    entry_at: datetime | None
    exit_at: datetime | None
    source: str


async def list_section_attendance(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    section_id: UUID,
    on_date: date,
) -> list[TeacherAttendanceRow]:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    tenant_id = ctx.tenant_id
    await assert_teacher_assigned_to_section(
        session,
        tenant_id=tenant_id,
        teacher_user_id=ctx.user_id,
        section_id=section_id,
    )
    student_ids = (
        await session.execute(
            select(Enrollment.student_id).where(
                Enrollment.tenant_id == tenant_id,
                Enrollment.section_id == section_id,
                Enrollment.status == "active",
                Enrollment.starts_on <= on_date,
            )
        )
    ).scalars().all()
    if not student_ids:
        return []
    records = (
        await session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.tenant_id == tenant_id,
                AttendanceRecord.student_id.in_(student_ids),
                AttendanceRecord.attendance_date == on_date,
            )
        )
    ).scalars().all()
    return [
        TeacherAttendanceRow(
            id=row.id,
            student_id=row.student_id,
            attendance_date=row.attendance_date,
            status=row.status,
            entry_at=row.entry_at,
            exit_at=row.exit_at,
            source=row.source,
        )
        for row in records
    ]


async def mark_student_attendance(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    section_id: UUID,
    student_id: UUID,
    on_date: date,
    status: str,
    entry_at: datetime | None,
    exit_at: datetime | None,
    reason: str | None,
    request_id: str | None,
) -> AttendanceRecord:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    if status not in ALLOWED_MARK_STATUSES:
        raise ValidationFailed("Invalid attendance status")
    tenant_id = ctx.tenant_id
    await assert_student_in_teacher_section(
        session,
        tenant_id=tenant_id,
        teacher_user_id=ctx.user_id,
        section_id=section_id,
        student_id=student_id,
        on_date=on_date,
    )
    enrollment = (
        await session.execute(
            select(Enrollment).where(
                Enrollment.tenant_id == tenant_id,
                Enrollment.student_id == student_id,
                Enrollment.section_id == section_id,
                Enrollment.status == "active",
            )
        )
    ).scalar_one()
    existing = (
        await session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.tenant_id == tenant_id,
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.attendance_date == on_date,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        record = AttendanceRecord(
            tenant_id=tenant_id,
            student_id=student_id,
            academic_year_id=enrollment.academic_year_id,
            attendance_date=on_date,
            status=status,
            entry_at=entry_at,
            exit_at=exit_at,
            source="manual_teacher",
            version=1,
        )
        session.add(record)
        await session.flush()
        return record
    if existing.source == "rfid" or existing.status != status or existing.entry_at != entry_at:
        correction_reason = (reason or "").strip() or "Teacher attendance correction"
        return await apply_correction(
            session,
            ctx,
            existing.id,
            new_status=status,
            new_entry_at=entry_at if entry_at is not None else existing.entry_at,
            new_exit_at=exit_at if exit_at is not None else existing.exit_at,
            reason=correction_reason,
            request_id=request_id,
        )
    existing.exit_at = exit_at
    existing.updated_at = utcnow()
    await session.flush()
    return existing
