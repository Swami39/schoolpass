"""Teacher class listing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.attendance.models import AttendanceRecord
from schoolpass.errors import NotFoundError
from schoolpass.people.models import Enrollment, SchoolClass, Section, Student
from schoolpass.teacher.access import load_teacher_staff
from schoolpass.teacher.models import Subject, TeacherSectionAssignment
from schoolpass.tenancy.context import TenantContext


@dataclass(frozen=True)
class TeacherClassSummary:
    section_id: UUID
    class_id: UUID
    class_name: str
    section_name: str
    subject_id: UUID | None
    subject_name: str | None
    academic_year_id: UUID
    student_count: int
    today_present_count: int
    today_absent_count: int


@dataclass(frozen=True)
class TeacherStudentSummary:
    student_id: UUID
    first_name: str
    middle_name: str | None
    last_name: str
    admission_no: str
    status: str


async def list_teacher_classes(
    session: AsyncSession,
    ctx: TenantContext,
) -> list[TeacherClassSummary]:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    tenant_id = ctx.tenant_id
    await load_teacher_staff(session, tenant_id=tenant_id, user_id=ctx.user_id)
    today = date.today()
    assignments = (
        await session.execute(
            select(TeacherSectionAssignment, Section, SchoolClass, Subject)
            .join(
                Section,
                (Section.id == TeacherSectionAssignment.section_id)
                & (Section.tenant_id == TeacherSectionAssignment.tenant_id),
            )
            .join(
                SchoolClass,
                (SchoolClass.id == Section.class_id) & (SchoolClass.tenant_id == Section.tenant_id),
            )
            .outerjoin(
                Subject,
                (Subject.id == TeacherSectionAssignment.subject_id)
                & (Subject.tenant_id == TeacherSectionAssignment.tenant_id),
            )
            .where(
                TeacherSectionAssignment.tenant_id == tenant_id,
                TeacherSectionAssignment.teacher_user_id == ctx.user_id,
                TeacherSectionAssignment.status == "active",
            )
            .order_by(SchoolClass.name, Section.name)
        )
    ).all()
    summaries: list[TeacherClassSummary] = []
    for assign, section, clazz, subject in assignments:
        student_count = (
            await session.execute(
                select(func.count())
                .select_from(Enrollment)
                .where(
                    Enrollment.tenant_id == tenant_id,
                    Enrollment.section_id == section.id,
                    Enrollment.status == "active",
                    Enrollment.starts_on <= today,
                )
            )
        ).scalar_one()
        present = (
            await session.execute(
                select(func.count())
                .select_from(AttendanceRecord)
                .join(
                    Enrollment,
                    (Enrollment.student_id == AttendanceRecord.student_id)
                    & (Enrollment.tenant_id == AttendanceRecord.tenant_id),
                )
                .where(
                    Enrollment.tenant_id == tenant_id,
                    Enrollment.section_id == section.id,
                    Enrollment.status == "active",
                    AttendanceRecord.attendance_date == today,
                    AttendanceRecord.status.in_(("present", "late")),
                )
            )
        ).scalar_one()
        absent = (
            await session.execute(
                select(func.count())
                .select_from(AttendanceRecord)
                .join(
                    Enrollment,
                    (Enrollment.student_id == AttendanceRecord.student_id)
                    & (Enrollment.tenant_id == AttendanceRecord.tenant_id),
                )
                .where(
                    Enrollment.tenant_id == tenant_id,
                    Enrollment.section_id == section.id,
                    Enrollment.status == "active",
                    AttendanceRecord.attendance_date == today,
                    AttendanceRecord.status == "absent",
                )
            )
        ).scalar_one()
        summaries.append(
            TeacherClassSummary(
                section_id=section.id,
                class_id=clazz.id,
                class_name=clazz.name,
                section_name=section.name,
                subject_id=subject.id if subject else None,
                subject_name=subject.name if subject else None,
                academic_year_id=assign.academic_year_id,
                student_count=student_count,
                today_present_count=present,
                today_absent_count=absent,
            )
        )
    return summaries


async def list_section_students(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    section_id: UUID,
) -> list[TeacherStudentSummary]:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    tenant_id = ctx.tenant_id
    from schoolpass.teacher.access import assert_teacher_assigned_to_section

    await assert_teacher_assigned_to_section(
        session,
        tenant_id=tenant_id,
        teacher_user_id=ctx.user_id,
        section_id=section_id,
    )
    today = date.today()
    rows = (
        await session.execute(
            select(Student)
            .join(
                Enrollment,
                (Enrollment.student_id == Student.id) & (Enrollment.tenant_id == Student.tenant_id),
            )
            .where(
                Enrollment.tenant_id == tenant_id,
                Enrollment.section_id == section_id,
                Enrollment.status == "active",
                Enrollment.starts_on <= today,
                Student.status == "active",
            )
            .order_by(Student.last_name, Student.first_name, Student.admission_no)
        )
    ).scalars().all()
    return [
        TeacherStudentSummary(
            student_id=row.id,
            first_name=row.first_name,
            middle_name=row.middle_name,
            last_name=row.last_name,
            admission_no=row.admission_no,
            status=row.status,
        )
        for row in rows
    ]
