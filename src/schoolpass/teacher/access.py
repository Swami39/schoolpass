"""Teacher identity and assignment authorization."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.errors import AuthorizationError, NotFoundError
from schoolpass.identity.models import StaffProfile
from schoolpass.people.models import Enrollment, Student
from schoolpass.teacher.models import TeacherSectionAssignment


async def load_teacher_staff(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
) -> StaffProfile:
    row = (
        await session.execute(
            select(StaffProfile).where(
                StaffProfile.tenant_id == tenant_id,
                StaffProfile.user_id == user_id,
                StaffProfile.staff_type == "teacher",
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError()
    return row


async def get_active_assignment(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    teacher_user_id: UUID,
    section_id: UUID,
) -> TeacherSectionAssignment:
    row = (
        await session.execute(
            select(TeacherSectionAssignment).where(
                TeacherSectionAssignment.tenant_id == tenant_id,
                TeacherSectionAssignment.teacher_user_id == teacher_user_id,
                TeacherSectionAssignment.section_id == section_id,
                TeacherSectionAssignment.status == "active",
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError()
    return row


async def assert_teacher_assigned_to_section(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    teacher_user_id: UUID,
    section_id: UUID,
) -> TeacherSectionAssignment:
    await load_teacher_staff(session, tenant_id=tenant_id, user_id=teacher_user_id)
    return await get_active_assignment(
        session,
        tenant_id=tenant_id,
        teacher_user_id=teacher_user_id,
        section_id=section_id,
    )


async def assert_student_in_teacher_section(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    teacher_user_id: UUID,
    section_id: UUID,
    student_id: UUID,
    on_date: date | None = None,
) -> None:
    await assert_teacher_assigned_to_section(
        session,
        tenant_id=tenant_id,
        teacher_user_id=teacher_user_id,
        section_id=section_id,
    )
    check_date = on_date or date.today()
    enrolled = (
        await session.execute(
            select(Enrollment.id).where(
                Enrollment.tenant_id == tenant_id,
                Enrollment.student_id == student_id,
                Enrollment.section_id == section_id,
                Enrollment.status == "active",
                Enrollment.starts_on <= check_date,
            )
        )
    ).scalar_one_or_none()
    if enrolled is None:
        raise NotFoundError()
    if on_date is not None:
        ends = (
            await session.execute(
                select(Enrollment.ends_on).where(
                    Enrollment.tenant_id == tenant_id,
                    Enrollment.student_id == student_id,
                    Enrollment.section_id == section_id,
                    Enrollment.status == "active",
                )
            )
        ).scalar_one_or_none()
        if ends is not None and ends < check_date:
            raise NotFoundError()
    student = await session.get(Student, student_id)
    if student is None or student.tenant_id != tenant_id or student.status != "active":
        raise NotFoundError()


async def assert_teacher_assigned_to_subject_section(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    teacher_user_id: UUID,
    section_id: UUID,
    subject_id: UUID,
) -> TeacherSectionAssignment:
    await load_teacher_staff(session, tenant_id=tenant_id, user_id=teacher_user_id)
    row = (
        await session.execute(
            select(TeacherSectionAssignment).where(
                TeacherSectionAssignment.tenant_id == tenant_id,
                TeacherSectionAssignment.teacher_user_id == teacher_user_id,
                TeacherSectionAssignment.section_id == section_id,
                TeacherSectionAssignment.status == "active",
                or_(
                    TeacherSectionAssignment.subject_id == subject_id,
                    TeacherSectionAssignment.subject_id.is_(None),
                ),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise AuthorizationError()
    if row.subject_id is not None and row.subject_id != subject_id:
        raise AuthorizationError()
    return row
