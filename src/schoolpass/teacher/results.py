"""Teacher result entry for assigned classes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.db.mixins import utcnow
from schoolpass.errors import ConflictError, NotFoundError, ValidationFailed
from schoolpass.teacher.access import (
    assert_student_in_teacher_section,
    assert_teacher_assigned_to_section,
    assert_teacher_assigned_to_subject_section,
)
from schoolpass.teacher.models import Assessment, StudentAssessmentMark, Subject
from schoolpass.tenancy.context import TenantContext


@dataclass(frozen=True)
class AssessmentSummary:
    id: UUID
    section_id: UUID
    subject_id: UUID
    subject_name: str
    code: str
    name: str
    max_marks: int
    scheduled_on: date | None


@dataclass(frozen=True)
class StudentMarkRow:
    student_id: UUID
    marks: int | None
    mark_id: UUID | None
    version: int | None


async def list_assessments_for_section(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    section_id: UUID,
    subject_id: UUID | None = None,
) -> list[AssessmentSummary]:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    tenant_id = ctx.tenant_id
    await assert_teacher_assigned_to_section(
        session,
        tenant_id=tenant_id,
        teacher_user_id=ctx.user_id,
        section_id=section_id,
    )
    stmt = (
        select(Assessment, Subject)
        .join(
            Subject,
            (Subject.id == Assessment.subject_id) & (Subject.tenant_id == Assessment.tenant_id),
        )
        .where(
            Assessment.tenant_id == tenant_id,
            Assessment.section_id == section_id,
            Assessment.status == "active",
        )
        .order_by(Assessment.scheduled_on.desc().nullslast(), Assessment.code)
    )
    if subject_id is not None:
        stmt = stmt.where(Assessment.subject_id == subject_id)
    rows = (await session.execute(stmt)).all()
    return [
        AssessmentSummary(
            id=assessment.id,
            section_id=assessment.section_id,
            subject_id=assessment.subject_id,
            subject_name=subject.name,
            code=assessment.code,
            name=assessment.name,
            max_marks=assessment.max_marks,
            scheduled_on=assessment.scheduled_on,
        )
        for assessment, subject in rows
    ]


async def list_marks_for_assessment(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    assessment_id: UUID,
) -> tuple[Assessment, list[StudentMarkRow]]:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    tenant_id = ctx.tenant_id
    assessment = await session.get(Assessment, assessment_id)
    if assessment is None or assessment.tenant_id != tenant_id:
        raise NotFoundError()
    await assert_teacher_assigned_to_subject_section(
        session,
        tenant_id=tenant_id,
        teacher_user_id=ctx.user_id,
        section_id=assessment.section_id,
        subject_id=assessment.subject_id,
    )
    marks = (
        await session.execute(
            select(StudentAssessmentMark).where(
                StudentAssessmentMark.tenant_id == tenant_id,
                StudentAssessmentMark.assessment_id == assessment_id,
            )
        )
    ).scalars().all()
    by_student = {m.student_id: m for m in marks}
    from schoolpass.teacher.classes import list_section_students

    students = await list_section_students(session, ctx, section_id=assessment.section_id)
    rows = [
        StudentMarkRow(
            student_id=s.student_id,
            marks=by_student[s.student_id].marks if s.student_id in by_student else None,
            mark_id=by_student[s.student_id].id if s.student_id in by_student else None,
            version=by_student[s.student_id].version if s.student_id in by_student else None,
        )
        for s in students
    ]
    return assessment, rows


async def upsert_student_mark(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    assessment_id: UUID,
    student_id: UUID,
    marks: int,
) -> StudentAssessmentMark:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    if marks < 0:
        raise ValidationFailed("Marks cannot be negative")
    tenant_id = ctx.tenant_id
    assessment = await session.get(Assessment, assessment_id)
    if assessment is None or assessment.tenant_id != tenant_id:
        raise NotFoundError()
    if marks > assessment.max_marks:
        raise ValidationFailed("Marks exceed maximum")
    await assert_teacher_assigned_to_subject_section(
        session,
        tenant_id=tenant_id,
        teacher_user_id=ctx.user_id,
        section_id=assessment.section_id,
        subject_id=assessment.subject_id,
    )
    await assert_student_in_teacher_section(
        session,
        tenant_id=tenant_id,
        teacher_user_id=ctx.user_id,
        section_id=assessment.section_id,
        student_id=student_id,
    )
    existing = (
        await session.execute(
            select(StudentAssessmentMark).where(
                StudentAssessmentMark.tenant_id == tenant_id,
                StudentAssessmentMark.assessment_id == assessment_id,
                StudentAssessmentMark.student_id == student_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        row = StudentAssessmentMark(
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            student_id=student_id,
            marks=marks,
            entered_by=ctx.user_id,
            version=1,
        )
        try:
            session.add(row)
            await session.flush()
        except IntegrityError:
            raise ConflictError("Duplicate result") from None
        return row
    existing.marks = marks
    existing.entered_by = ctx.user_id
    existing.version += 1
    existing.updated_at = utcnow()
    await session.flush()
    return existing
