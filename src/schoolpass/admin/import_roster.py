"""Single-file school roster import: classes, teachers, students, and parents."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.admin import academic as admin_academic
from schoolpass.admin import staff as staff_admin
from schoolpass.admin.academic_schemas import (
    AcademicYearCreateRequest,
    SchoolClassCreateRequest,
    SectionCreateRequest,
    SubjectCreateRequest,
    TeacherAssignmentCreateRequest,
)
from schoolpass.admin.directory import ensure_user_with_role
from schoolpass.admin.import_schemas import ImportRowError
from schoolpass.errors import ConflictError
from schoolpass.identity.models import StaffProfile
from schoolpass.people import services as people_svc
from schoolpass.people.models import AcademicYear, Guardian, SchoolClass, Section, Student
from schoolpass.teacher.models import Subject, TeacherSectionAssignment
from schoolpass.tenancy.context import TenantContext

ROSTER_COLUMNS: list[str] = [
    "academic_year_code",
    "academic_year_name",
    "year_starts_on",
    "year_ends_on",
    "class_code",
    "class_name",
    "section_name",
    "teacher_email",
    "subject_code",
    "subject_name",
    "admission_no",
    "student_first_name",
    "student_middle_name",
    "student_last_name",
    "student_dob",
    "parent_email",
    "parent_first_name",
    "parent_last_name",
    "parent_phone",
    "relationship_type",
]

ROSTER_REQUIRED = frozenset(
    {
        "academic_year_code",
        "class_code",
        "section_name",
        "admission_no",
        "student_first_name",
        "student_last_name",
        "parent_email",
        "parent_first_name",
        "parent_last_name",
    }
)

SAMPLE_ROSTER_CSV = """academic_year_code,academic_year_name,year_starts_on,year_ends_on,class_code,class_name,section_name,teacher_email,subject_code,subject_name,admission_no,student_first_name,student_middle_name,student_last_name,student_dob,parent_email,parent_first_name,parent_last_name,parent_phone,relationship_type
2026-27,Academic Year 2026-27,2026-04-01,2027-03-31,10,Class 10,A,demo.teacher@schoolpass.local,MATH,Mathematics,SP-1001,Asha,,Kumar,2014-06-01,parent.asha@schoolpass.local,Ravi,Kumar,+919876543210,parent
2026-27,Academic Year 2026-27,2026-04-01,2027-03-31,10,Class 10,A,demo.teacher@schoolpass.local,MATH,Mathematics,SP-1002,Neel,,Shah,2014-08-12,parent.neel@schoolpass.local,Meera,Shah,+919876543211,parent
"""


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


async def validate_roster_rows(
    session: AsyncSession,
    ctx: TenantContext,
    rows: list[dict[str, str]],
    errors: list[ImportRowError],
) -> int:
    del session, ctx
    valid = 0
    seen_admissions: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        missing = [col for col in ROSTER_REQUIRED if not row.get(col)]
        if missing:
            errors.append(ImportRowError(row_number=idx, message=f"missing {', '.join(missing)}"))
            continue
        admission = row["admission_no"]
        if admission in seen_admissions:
            errors.append(ImportRowError(row_number=idx, message="duplicate admission_no in file"))
            continue
        seen_admissions.add(admission)
        for field in ("year_starts_on", "year_ends_on", "student_dob"):
            raw = row.get(field, "")
            if not raw:
                continue
            try:
                _parse_date(raw)
            except ValueError:
                errors.append(ImportRowError(row_number=idx, message=f"{field} must be YYYY-MM-DD"))
                break
        else:
            valid += 1
    return valid


async def _get_or_create_year(
    session: AsyncSession,
    ctx: TenantContext,
    row: dict[str, str],
    *,
    request_id: str | None,
) -> AcademicYear:
    tenant_id = ctx.tenant_id
    assert tenant_id is not None
    code = row["academic_year_code"]
    existing = (
        await session.execute(select(AcademicYear).where(AcademicYear.tenant_id == tenant_id, AcademicYear.code == code))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    starts = _parse_date(row.get("year_starts_on", "")) or date(date.today().year, 4, 1)
    ends = _parse_date(row.get("year_ends_on", "")) or date(starts.year + 1, 3, 31)
    name = row.get("academic_year_name") or code
    return await admin_academic.create_academic_year(
        session,
        ctx,
        AcademicYearCreateRequest(code=code, name=name, starts_on=starts, ends_on=ends),
        request_id=request_id,
    )


async def _get_or_create_class(
    session: AsyncSession,
    ctx: TenantContext,
    row: dict[str, str],
    *,
    request_id: str | None,
) -> SchoolClass:
    tenant_id = ctx.tenant_id
    assert tenant_id is not None
    code = row["class_code"]
    existing = (
        await session.execute(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id, SchoolClass.code == code))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    return await admin_academic.create_class(
        session,
        ctx,
        SchoolClassCreateRequest(code=code, name=row.get("class_name") or f"Class {code}"),
        request_id=request_id,
    )


async def _get_or_create_section(
    session: AsyncSession,
    ctx: TenantContext,
    school_class: SchoolClass,
    name: str,
    *,
    request_id: str | None,
) -> Section:
    tenant_id = ctx.tenant_id
    assert tenant_id is not None
    existing = (
        await session.execute(
            select(Section).where(
                Section.tenant_id == tenant_id,
                Section.class_id == school_class.id,
                Section.name == name,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    return await admin_academic.create_section(
        session,
        ctx,
        SectionCreateRequest(class_id=school_class.id, name=name),
        request_id=request_id,
    )


async def _get_or_create_subject(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    code: str,
    name: str,
    request_id: str | None,
) -> Subject:
    tenant_id = ctx.tenant_id
    assert tenant_id is not None
    existing = (
        await session.execute(select(Subject).where(Subject.tenant_id == tenant_id, Subject.code == code))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    return await admin_academic.create_subject(
        session,
        ctx,
        SubjectCreateRequest(code=code, name=name or code),
        request_id=request_id,
    )


async def _ensure_teacher_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    row: dict[str, str],
    *,
    year: AcademicYear,
    section: Section,
    request_id: str | None,
) -> None:
    email = (row.get("teacher_email") or "").strip()
    if not email:
        return
    tenant_id = ctx.tenant_id
    assert tenant_id is not None
    user = await ensure_user_with_role(session, ctx, email=email, role_name="teacher")
    staff = (
        await session.execute(
            select(StaffProfile).where(StaffProfile.tenant_id == tenant_id, StaffProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if staff is None:
        await staff_admin.create_staff(
            session,
            ctx,
            user_id=user.id,
            staff_type="teacher",
            employee_code=None,
            request_id=request_id,
        )
    subject = None
    subject_code = (row.get("subject_code") or "").strip()
    if subject_code:
        subject = await _get_or_create_subject(
            session,
            ctx,
            code=subject_code,
            name=row.get("subject_name") or subject_code,
            request_id=request_id,
        )
    existing = (
        await session.execute(
            select(TeacherSectionAssignment).where(
                TeacherSectionAssignment.tenant_id == tenant_id,
                TeacherSectionAssignment.teacher_user_id == user.id,
                TeacherSectionAssignment.academic_year_id == year.id,
                TeacherSectionAssignment.section_id == section.id,
                TeacherSectionAssignment.subject_id == (subject.id if subject else None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    try:
        await admin_academic.create_teacher_assignment(
            session,
            ctx,
            TeacherAssignmentCreateRequest(
                teacher_user_id=user.id,
                academic_year_id=year.id,
                section_id=section.id,
                subject_id=subject.id if subject else None,
                assignment_role="class_teacher" if subject is None else "subject_teacher",
            ),
            request_id=request_id,
        )
    except ConflictError:
        return


async def _get_or_create_student(
    session: AsyncSession,
    ctx: TenantContext,
    row: dict[str, str],
    *,
    request_id: str | None,
) -> tuple[Student, bool]:
    tenant_id = ctx.tenant_id
    assert tenant_id is not None
    admission = row["admission_no"]
    existing = (
        await session.execute(select(Student).where(Student.tenant_id == tenant_id, Student.admission_no == admission))
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False
    dob = None
    try:
        dob = _parse_date(row.get("student_dob", ""))
    except ValueError:
        dob = None
    created = await people_svc.create_student(
        session,
        ctx,
        admission_no=admission,
        first_name=row["student_first_name"],
        middle_name=row.get("student_middle_name") or None,
        last_name=row["student_last_name"],
        date_of_birth=dob,
        photo_file_id=None,
        request_id=request_id,
    )
    return created, True


async def _get_or_create_guardian(
    session: AsyncSession,
    ctx: TenantContext,
    row: dict[str, str],
    *,
    request_id: str | None,
) -> Guardian:
    tenant_id = ctx.tenant_id
    assert tenant_id is not None
    email = row["parent_email"].strip().lower()
    existing = (
        await session.execute(select(Guardian).where(Guardian.tenant_id == tenant_id, Guardian.email == email))
    ).scalar_one_or_none()
    if existing is None:
        existing = await people_svc.create_guardian(
            session,
            ctx,
            first_name=row["parent_first_name"],
            last_name=row["parent_last_name"],
            phone_e164=row.get("parent_phone") or None,
            email=email,
            request_id=request_id,
            create_parent_login=True,
        )
        return existing
    user = await ensure_user_with_role(
        session,
        ctx,
        email=email,
        role_name="parent",
        phone_e164=row.get("parent_phone") or None,
    )
    if existing.user_id != user.id:
        existing.user_id = user.id
        await session.flush()
    return existing


async def apply_roster_rows(
    session: AsyncSession,
    ctx: TenantContext,
    rows: list[dict[str, str]],
    *,
    request_id: str | None,
) -> tuple[int, int]:
    applied = 0
    skipped = 0
    for row in rows:
        year = await _get_or_create_year(session, ctx, row, request_id=request_id)
        school_class = await _get_or_create_class(session, ctx, row, request_id=request_id)
        section = await _get_or_create_section(
            session, ctx, school_class, row["section_name"], request_id=request_id
        )
        await _ensure_teacher_assignment(session, ctx, row, year=year, section=section, request_id=request_id)
        student, created_student = await _get_or_create_student(session, ctx, row, request_id=request_id)
        enrollments = await people_svc.list_enrollments_for_student(session, ctx, student.id)
        has_active = any(e.status == "active" and e.section_id == section.id for e in enrollments)
        if not has_active:
            try:
                await people_svc.create_enrollment(
                    session,
                    ctx,
                    student_id=student.id,
                    academic_year_id=year.id,
                    class_id=school_class.id,
                    section_id=section.id,
                    starts_on=_parse_date(row.get("year_starts_on", "")) or year.starts_on,
                    request_id=request_id,
                )
            except ConflictError:
                pass
        guardian = await _get_or_create_guardian(session, ctx, row, request_id=request_id)
        links = await people_svc.list_student_guardians(session, ctx, student.id)
        if not any(link.guardian_id == guardian.id for link in links):
            await people_svc.attach_guardian(
                session,
                ctx,
                student_id=student.id,
                guardian_id=guardian.id,
                relationship_type=row.get("relationship_type") or "parent",
                is_primary_contact=True,
                can_receive_notifications=True,
                can_pay_fees=True,
                request_id=request_id,
            )
            applied += 1
        elif created_student:
            applied += 1
        else:
            skipped += 1
    return applied, skipped
