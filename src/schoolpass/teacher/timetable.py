"""Teacher timetable read/update."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.db.mixins import utcnow
from schoolpass.errors import ConflictError, NotFoundError, ValidationFailed
from schoolpass.people.models import SchoolClass, Section
from schoolpass.teacher.access import assert_teacher_assigned_to_section, load_teacher_staff
from schoolpass.teacher.models import Subject, TimetablePeriod
from schoolpass.tenancy.context import TenantContext


@dataclass(frozen=True)
class TimetablePeriodRow:
    id: UUID
    section_id: UUID
    class_name: str
    section_name: str
    day_of_week: int
    period_number: int
    starts_at: time
    ends_at: time
    subject_id: UUID
    subject_name: str


async def list_teacher_timetable(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    academic_year_id: UUID | None = None,
) -> list[TimetablePeriodRow]:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    tenant_id = ctx.tenant_id
    await load_teacher_staff(session, tenant_id=tenant_id, user_id=ctx.user_id)
    stmt = (
        select(TimetablePeriod, Section, SchoolClass, Subject)
        .join(
            Section,
            (Section.id == TimetablePeriod.section_id) & (Section.tenant_id == TimetablePeriod.tenant_id),
        )
        .join(
            SchoolClass,
            (SchoolClass.id == Section.class_id) & (SchoolClass.tenant_id == Section.tenant_id),
        )
        .join(
            Subject,
            (Subject.id == TimetablePeriod.subject_id) & (Subject.tenant_id == TimetablePeriod.tenant_id),
        )
        .where(
            TimetablePeriod.tenant_id == tenant_id,
            TimetablePeriod.teacher_user_id == ctx.user_id,
        )
        .order_by(TimetablePeriod.day_of_week, TimetablePeriod.period_number)
    )
    if academic_year_id is not None:
        stmt = stmt.where(TimetablePeriod.academic_year_id == academic_year_id)
    rows = (await session.execute(stmt)).all()
    return [
        TimetablePeriodRow(
            id=period.id,
            section_id=section.id,
            class_name=clazz.name,
            section_name=section.name,
            day_of_week=period.day_of_week,
            period_number=period.period_number,
            starts_at=period.starts_at,
            ends_at=period.ends_at,
            subject_id=subject.id,
            subject_name=subject.name,
        )
        for period, section, clazz, subject in rows
    ]


async def update_timetable_period(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    period_id: UUID,
    starts_at: time | None,
    ends_at: time | None,
    subject_id: UUID | None,
    teacher_user_id: UUID | None,
) -> TimetablePeriod:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    tenant_id = ctx.tenant_id
    period = await session.get(TimetablePeriod, period_id)
    if period is None or period.tenant_id != tenant_id:
        raise NotFoundError()
    if period.teacher_user_id != ctx.user_id:
        await assert_teacher_assigned_to_section(
            session,
            tenant_id=tenant_id,
            teacher_user_id=ctx.user_id,
            section_id=period.section_id,
        )
    if starts_at is not None:
        period.starts_at = starts_at
    if ends_at is not None:
        period.ends_at = ends_at
    if subject_id is not None:
        period.subject_id = subject_id
    if teacher_user_id is not None:
        period.teacher_user_id = teacher_user_id
    if period.ends_at <= period.starts_at:
        raise ValidationFailed("Period end must be after start")
    conflict = (
        await session.execute(
            select(TimetablePeriod.id).where(
                TimetablePeriod.tenant_id == tenant_id,
                TimetablePeriod.academic_year_id == period.academic_year_id,
                TimetablePeriod.section_id == period.section_id,
                TimetablePeriod.day_of_week == period.day_of_week,
                TimetablePeriod.period_number == period.period_number,
                TimetablePeriod.id != period.id,
            )
        )
    ).scalar_one_or_none()
    if conflict is not None:
        raise ConflictError("Timetable slot conflict")
    period.version += 1
    period.updated_at = utcnow()
    await session.flush()
    return period
