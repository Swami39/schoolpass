from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.attendance.engine import process_observation
from schoolpass.attendance.models import (
    AttendanceCorrection,
    AttendanceDailyRun,
    AttendancePolicy,
    AttendanceRecord,
)
from schoolpass.attendance.rules import is_weekend, policy_covers_date
from schoolpass.audit.service import record_audit
from schoolpass.db.mixins import utcnow
from schoolpass.errors import NotFoundError, ValidationFailed
from schoolpass.observability.metrics import metrics
from schoolpass.outbox.service import enqueue_outbox
from schoolpass.people.models import Enrollment, Student
from schoolpass.people.pagination import decode_cursor, encode_cursor
from schoolpass.tenancy.context import TenantContext

MAX_PAGE = 200


def _require_tenant(ctx: TenantContext) -> UUID:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    return ctx.tenant_id


async def create_policy(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    name: str,
    effective_from: date,
    effective_to: date | None,
    entry_start_time: time | None,
    present_until: time | None,
    late_until: time | None,
    entry_dedupe_seconds: int,
    exit_dedupe_seconds: int,
    request_id: str | None,
) -> AttendancePolicy:
    tenant_id = _require_tenant(ctx)
    row = AttendancePolicy(
        tenant_id=tenant_id,
        name=name,
        effective_from=effective_from,
        effective_to=effective_to,
        entry_start_time=entry_start_time,
        present_until=present_until,
        late_until=late_until,
        entry_dedupe_seconds=entry_dedupe_seconds,
        exit_dedupe_seconds=exit_dedupe_seconds,
    )
    session.add(row)
    await session.flush()
    await record_audit(
        session,
        ctx,
        action="attendance.policy_created",
        resource_type="attendance_policy",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def list_policies(session: AsyncSession, ctx: TenantContext) -> list[AttendancePolicy]:
    _require_tenant(ctx)
    result = await session.execute(
        select(AttendancePolicy).order_by(AttendancePolicy.effective_from.desc())
    )
    return list(result.scalars())


async def patch_policy(
    session: AsyncSession,
    ctx: TenantContext,
    policy_id: UUID,
    *,
    name: str | None,
    effective_to: date | None,
    entry_start_time: time | None,
    present_until: time | None,
    late_until: time | None,
    entry_dedupe_seconds: int | None,
    exit_dedupe_seconds: int | None,
    request_id: str | None,
) -> AttendancePolicy:
    row = await session.get(AttendancePolicy, policy_id)
    if row is None:
        raise NotFoundError()
    if name is not None:
        row.name = name
    if effective_to is not None:
        row.effective_to = effective_to
    if entry_start_time is not None:
        row.entry_start_time = entry_start_time
    if present_until is not None:
        row.present_until = present_until
    if late_until is not None:
        row.late_until = late_until
    if entry_dedupe_seconds is not None:
        row.entry_dedupe_seconds = entry_dedupe_seconds
    if exit_dedupe_seconds is not None:
        row.exit_dedupe_seconds = exit_dedupe_seconds
    row.updated_at = utcnow()
    await session.flush()
    await record_audit(
        session,
        ctx,
        action="attendance.policy_updated",
        resource_type="attendance_policy",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def get_record(session: AsyncSession, ctx: TenantContext, record_id: UUID) -> AttendanceRecord:
    row = await session.get(AttendanceRecord, record_id)
    if row is None:
        raise NotFoundError()
    return row


async def list_records(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    on_date: date | None,
    from_date: date | None,
    to_date: date | None,
    student_id: UUID | None,
    status: str | None,
    section_id: UUID | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[AttendanceRecord], str | None]:
    limit = min(max(limit, 1), MAX_PAGE)
    stmt = select(AttendanceRecord).order_by(
        AttendanceRecord.attendance_date.desc(),
        AttendanceRecord.id.desc(),
    )
    if on_date:
        stmt = stmt.where(AttendanceRecord.attendance_date == on_date)
    if from_date:
        stmt = stmt.where(AttendanceRecord.attendance_date >= from_date)
    if to_date:
        stmt = stmt.where(AttendanceRecord.attendance_date <= to_date)
    if student_id:
        stmt = stmt.where(AttendanceRecord.student_id == student_id)
    if status:
        stmt = stmt.where(AttendanceRecord.status == status)
    if section_id:
        stmt = stmt.join(
            Enrollment,
            and_(
                Enrollment.student_id == AttendanceRecord.student_id,
                Enrollment.tenant_id == AttendanceRecord.tenant_id,
            ),
        ).where(Enrollment.section_id == section_id)
    if cursor:
        decoded = decode_cursor(cursor)
        created = decoded[0] if decoded else None
        if created:
            stmt = stmt.where(AttendanceRecord.attendance_date <= created.date())
    stmt = stmt.limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(created_at=datetime.combine(last.attendance_date, time.min), row_id=last.id)
        rows = rows[:limit]
    return rows, next_cursor


async def attendance_summary(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    on_date: date,
) -> dict[str, int]:
    _require_tenant(ctx)
    stmt = (
        select(AttendanceRecord.status, func.count())
        .where(AttendanceRecord.attendance_date == on_date)
        .group_by(AttendanceRecord.status)
    )
    counts = {status: count for status, count in (await session.execute(stmt)).all()}
    return {
        "present": counts.get("present", 0),
        "late": counts.get("late", 0),
        "absent": counts.get("absent", 0),
        "excused": counts.get("excused", 0),
        "corrected": counts.get("corrected", 0),
        "unresolved": 0,
    }


async def apply_correction(
    session: AsyncSession,
    ctx: TenantContext,
    record_id: UUID,
    *,
    new_status: str,
    new_entry_at: datetime | None,
    new_exit_at: datetime | None,
    reason: str,
    request_id: str | None,
) -> AttendanceRecord:
    tenant_id = _require_tenant(ctx)
    if ctx.user_id is None:
        raise ValidationFailed("User context required for corrections")
    if not reason.strip():
        raise ValidationFailed("Correction reason is required")
    record = await get_record(session, ctx, record_id)
    correction = AttendanceCorrection(
        tenant_id=tenant_id,
        attendance_record_id=record.id,
        previous_status=record.status,
        new_status=new_status,
        previous_entry_at=record.entry_at,
        new_entry_at=new_entry_at,
        previous_exit_at=record.exit_at,
        new_exit_at=new_exit_at,
        reason=reason.strip(),
        corrected_by=ctx.user_id,
        created_at=utcnow(),
    )
    session.add(correction)
    record.status = new_status
    record.entry_at = new_entry_at
    record.exit_at = new_exit_at
    record.version += 1
    record.updated_at = utcnow()
    await session.flush()
    metrics.increment("attendance_corrections_total")
    await record_audit(
        session,
        ctx,
        action="attendance.corrected",
        resource_type="attendance_record",
        resource_id=record.id,
        request_id=request_id,
        metadata={"version": record.version},
    )
    await enqueue_outbox(
        session,
        topic="attendance.corrected",
        idempotency_key=f"attendance.corrected:{record.id}:{record.version}",
        tenant_id=tenant_id,
        correlation_id=request_id,
        payload={
            "attendance_id": str(record.id),
            "student_id": str(record.student_id),
            "attendance_date": record.attendance_date.isoformat(),
            "version": record.version,
        },
    )
    return record


async def finalize_attendance_for_date(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    attendance_date: date,
    request_id: str | None,
) -> AttendanceDailyRun:
    tenant_id = _require_tenant(ctx)
    if is_weekend(attendance_date):
        raise ValidationFailed("Cannot finalize a weekend date")
    existing_run = await session.execute(
        select(AttendanceDailyRun).where(
            AttendanceDailyRun.tenant_id == tenant_id,
            AttendanceDailyRun.attendance_date == attendance_date,
        )
    )
    run = existing_run.scalar_one_or_none()
    if run is not None and run.status == "completed":
        return run

    policy = None
    policies = await session.execute(select(AttendancePolicy).where(AttendancePolicy.tenant_id == tenant_id))
    for p in policies.scalars():
        if policy_covers_date(p, attendance_date):
            policy = p
            break
    if policy is None:
        raise ValidationFailed("No attendance policy for date")

    if run is None:
        run = AttendanceDailyRun(
            tenant_id=tenant_id,
            attendance_date=attendance_date,
            status="running",
            started_at=utcnow(),
            created_at=utcnow(),
        )
        session.add(run)
        await session.flush()
    else:
        run.status = "running"
        run.started_at = utcnow()

    enrollments = await session.execute(
        select(Enrollment).where(
            Enrollment.tenant_id == tenant_id,
            Enrollment.starts_on <= attendance_date,
            Enrollment.status == "active",
        )
    )
    for enrollment in enrollments.scalars():
        if enrollment.ends_on is not None and enrollment.ends_on < attendance_date:
            continue
        student = await session.get(Student, enrollment.student_id)
        if student is None or student.status == "withdrawn":
            continue
        existing = await session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.tenant_id == tenant_id,
                AttendanceRecord.student_id == enrollment.student_id,
                AttendanceRecord.attendance_date == attendance_date,
            )
        )
        record = existing.scalar_one_or_none()
        if record is None or record.entry_at is None:
            if record is None:
                record = AttendanceRecord(
                    tenant_id=tenant_id,
                    student_id=enrollment.student_id,
                    academic_year_id=enrollment.academic_year_id,
                    attendance_date=attendance_date,
                    status="absent",
                    source="finalization",
                    version=1,
                )
                session.add(record)
            elif record.status not in {"absent", "excused"}:
                record.status = "absent"
                record.updated_at = utcnow()

    run.status = "completed"
    run.completed_at = utcnow()
    await session.flush()
    metrics.increment("attendance_finalization_total")
    await record_audit(
        session,
        ctx,
        action="attendance.finalized",
        resource_type="attendance_daily_run",
        resource_id=run.id,
        request_id=request_id,
        metadata={"attendance_date": attendance_date.isoformat()},
    )
    return run


async def reprocess_observation(
    session: AsyncSession,
    ctx: TenantContext,
    observation_id: UUID,
) -> Any:
    tenant_id = _require_tenant(ctx)
    return await process_observation(session, tenant_id=tenant_id, observation_id=observation_id)
