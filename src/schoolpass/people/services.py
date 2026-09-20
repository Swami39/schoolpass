from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.audit.service import record_audit
from schoolpass.errors import ConflictError, NotFoundError, ValidationFailed
from schoolpass.outbox.service import enqueue_outbox
from schoolpass.people.models import (
    AcademicYear,
    Enrollment,
    Guardian,
    SchoolClass,
    Section,
    Student,
    StudentGuardian,
)
from schoolpass.people.pagination import decode_cursor, encode_cursor
from schoolpass.tenancy.context import TenantContext

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _tenant_id(ctx: TenantContext) -> UUID:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    return ctx.tenant_id


async def _require_student_in_tenant(session: AsyncSession, ctx: TenantContext, student_id: UUID) -> Student:
    row = await session.get(Student, student_id)
    if row is None or row.tenant_id != _tenant_id(ctx):
        raise NotFoundError()
    return row


async def _require_guardian_in_tenant(session: AsyncSession, ctx: TenantContext, guardian_id: UUID) -> Guardian:
    row = await session.get(Guardian, guardian_id)
    if row is None or row.tenant_id != _tenant_id(ctx):
        raise NotFoundError()
    return row


async def _require_enrollment_in_tenant(session: AsyncSession, ctx: TenantContext, enrollment_id: UUID) -> Enrollment:
    row = await session.get(Enrollment, enrollment_id)
    if row is None or row.tenant_id != _tenant_id(ctx):
        raise NotFoundError()
    return row


async def _validate_enrollment_placement(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    academic_year_id: UUID,
    class_id: UUID,
    section_id: UUID,
) -> None:
    tenant_id = _tenant_id(ctx)
    year = await session.get(AcademicYear, academic_year_id)
    if year is None or year.tenant_id != tenant_id:
        raise NotFoundError()
    clazz = await session.get(SchoolClass, class_id)
    if clazz is None or clazz.tenant_id != tenant_id:
        raise NotFoundError()
    section = await session.get(Section, section_id)
    if section is None or section.tenant_id != tenant_id:
        raise NotFoundError()
    if section.class_id != class_id:
        raise ValidationFailed("Section does not belong to the selected class")


async def _audit(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    action: str,
    resource_type: str,
    resource_id: UUID,
    request_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await record_audit(
        session,
        ctx,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        metadata=metadata or {},
    )


async def create_student(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    admission_no: str,
    first_name: str,
    middle_name: str | None,
    last_name: str,
    date_of_birth: date | None,
    photo_file_id: UUID | None,
    request_id: str | None,
) -> Student:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    row = Student(
        tenant_id=ctx.tenant_id,
        historical_subject_id=uuid4(),
        admission_no=admission_no,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        photo_file_id=photo_file_id,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Student could not be created") from exc
    await _audit(
        session,
        ctx,
        action="student.created",
        resource_type="student",
        resource_id=row.id,
        request_id=request_id,
        metadata={"admission_no": admission_no},
    )
    await enqueue_outbox(
        session,
        topic="student.created",
        idempotency_key=f"student.created:{row.id}",
        tenant_id=ctx.tenant_id,
        correlation_id=request_id,
        payload={"student_id": str(row.id), "historical_subject_id": str(row.historical_subject_id)},
    )
    return row


async def get_student(session: AsyncSession, ctx: TenantContext, student_id: UUID) -> Student:
    row = await session.get(Student, student_id)
    if row is None:
        raise NotFoundError()
    return row


async def update_student(
    session: AsyncSession,
    ctx: TenantContext,
    student_id: UUID,
    *,
    fields: dict[str, Any],
    request_id: str | None,
) -> Student:
    row = await get_student(session, ctx, student_id)
    if row.pii_state == "anonymized":
        raise ConflictError("Student is anonymized")
    for key, value in fields.items():
        if value is not None and hasattr(row, key):
            setattr(row, key, value)
    await session.flush()
    await _audit(
        session,
        ctx,
        action="student.updated",
        resource_type="student",
        resource_id=row.id,
        request_id=request_id,
        metadata={"fields": sorted(fields.keys())},
    )
    await enqueue_outbox(
        session,
        topic="student.updated",
        idempotency_key=f"student.updated:{row.id}:{row.updated_at.isoformat()}",
        tenant_id=ctx.tenant_id,
        correlation_id=request_id,
        payload={"student_id": str(row.id)},
    )
    return row


async def list_students(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    status: str | None,
    include_hidden: bool,
    search: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[Student], str | None]:
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    stmt = select(Student).order_by(Student.created_at.desc(), Student.id.desc())
    if status:
        stmt = stmt.where(Student.status == status)
    if not include_hidden:
        stmt = stmt.where(Student.pii_state == "active")
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Student.first_name.ilike(pattern),
                Student.last_name.ilike(pattern),
                Student.admission_no.ilike(pattern),
            )
        )
    decoded = decode_cursor(cursor) if cursor else None
    if decoded:
        created_at, row_id = decoded
        stmt = stmt.where(
            or_(
                Student.created_at < created_at,
                and_(Student.created_at == created_at, Student.id < row_id),
            )
        )
    stmt = stmt.limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(created_at=last.created_at, row_id=last.id)
        rows = rows[:limit]
    return rows, next_cursor


async def withdraw_student(
    session: AsyncSession,
    ctx: TenantContext,
    student_id: UUID,
    *,
    request_id: str | None,
) -> Student:
    row = await get_student(session, ctx, student_id)
    row.status = "withdrawn"
    await session.flush()
    await _audit(
        session,
        ctx,
        action="student.withdrawn",
        resource_type="student",
        resource_id=row.id,
        request_id=request_id,
    )
    await enqueue_outbox(
        session,
        topic="student.withdrawn",
        idempotency_key=f"student.withdrawn:{row.id}",
        tenant_id=ctx.tenant_id,
        correlation_id=request_id,
        payload={"student_id": str(row.id)},
    )
    return row


async def hide_student(
    session: AsyncSession,
    ctx: TenantContext,
    student_id: UUID,
    *,
    request_id: str | None,
) -> Student:
    row = await get_student(session, ctx, student_id)
    if row.pii_state == "anonymized":
        raise ConflictError("Student is anonymized")
    row.pii_state = "hidden"
    await session.flush()
    await _audit(
        session,
        ctx,
        action="student.hidden",
        resource_type="student",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def anonymize_student(
    session: AsyncSession,
    ctx: TenantContext,
    student_id: UUID,
    *,
    request_id: str | None,
) -> Student:
    row = await get_student(session, ctx, student_id)
    row.first_name = "Former"
    row.middle_name = None
    row.last_name = "Student"
    row.date_of_birth = None
    row.photo_file_id = None
    row.pii_state = "anonymized"
    row.status = "withdrawn"
    await session.flush()
    await _audit(
        session,
        ctx,
        action="student.anonymized",
        resource_type="student",
        resource_id=row.id,
        request_id=request_id,
    )
    await enqueue_outbox(
        session,
        topic="student.anonymized",
        idempotency_key=f"student.anonymized:{row.id}",
        tenant_id=ctx.tenant_id,
        correlation_id=request_id,
        payload={"student_id": str(row.id), "historical_subject_id": str(row.historical_subject_id)},
    )
    return row


async def create_guardian(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    first_name: str,
    last_name: str,
    phone_e164: str | None,
    email: str | None,
    request_id: str | None,
    create_parent_login: bool = True,
) -> Guardian:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    row = Guardian(
        tenant_id=ctx.tenant_id,
        first_name=first_name,
        last_name=last_name,
        phone_e164=phone_e164,
        email=email,
    )
    session.add(row)
    await session.flush()
    if create_parent_login and email:
        from schoolpass.admin.directory import ensure_user_with_role

        user = await ensure_user_with_role(
            session,
            ctx,
            email=email,
            role_name="parent",
            phone_e164=phone_e164,
        )
        row.user_id = user.id
        await session.flush()
    await _audit(
        session,
        ctx,
        action="guardian.created",
        resource_type="guardian",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def get_guardian(session: AsyncSession, ctx: TenantContext, guardian_id: UUID) -> Guardian:
    row = await session.get(Guardian, guardian_id)
    if row is None:
        raise NotFoundError()
    return row


async def update_guardian(
    session: AsyncSession,
    ctx: TenantContext,
    guardian_id: UUID,
    *,
    fields: dict[str, Any],
    request_id: str | None,
) -> Guardian:
    row = await get_guardian(session, ctx, guardian_id)
    for key, value in fields.items():
        if value is not None and hasattr(row, key):
            setattr(row, key, value)
    await session.flush()
    await _audit(
        session,
        ctx,
        action="guardian.updated",
        resource_type="guardian",
        resource_id=row.id,
        request_id=request_id,
        metadata={"fields": sorted(fields.keys())},
    )
    return row


async def list_guardians(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    limit: int,
    cursor: str | None,
) -> tuple[list[Guardian], str | None]:
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    stmt = select(Guardian).order_by(Guardian.created_at.desc(), Guardian.id.desc())
    decoded = decode_cursor(cursor) if cursor else None
    if decoded:
        created_at, row_id = decoded
        stmt = stmt.where(
            or_(
                Guardian.created_at < created_at,
                and_(Guardian.created_at == created_at, Guardian.id < row_id),
            )
        )
    stmt = stmt.limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(created_at=last.created_at, row_id=last.id)
        rows = rows[:limit]
    return rows, next_cursor


async def list_guardian_students(
    session: AsyncSession,
    ctx: TenantContext,
    guardian_id: UUID,
) -> list[StudentGuardian]:
    await get_guardian(session, ctx, guardian_id)
    result = await session.execute(
        select(StudentGuardian)
        .where(StudentGuardian.guardian_id == guardian_id, StudentGuardian.status == "active")
        .order_by(StudentGuardian.created_at.desc())
    )
    return list(result.scalars())


async def attach_guardian(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    student_id: UUID,
    guardian_id: UUID,
    relationship_type: str,
    is_primary_contact: bool,
    can_receive_notifications: bool,
    can_pay_fees: bool,
    request_id: str | None,
) -> StudentGuardian:
    await _require_student_in_tenant(session, ctx, student_id)
    await _require_guardian_in_tenant(session, ctx, guardian_id)
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    row = StudentGuardian(
        tenant_id=ctx.tenant_id,
        student_id=student_id,
        guardian_id=guardian_id,
        relationship_type=relationship_type,
        is_primary_contact=is_primary_contact,
        can_receive_notifications=can_receive_notifications,
        can_pay_fees=can_pay_fees,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Relationship already exists") from exc
    await _audit(
        session,
        ctx,
        action="student_guardian.created",
        resource_type="student_guardian",
        resource_id=row.id,
        request_id=request_id,
        metadata={"student_id": str(student_id), "guardian_id": str(guardian_id)},
    )
    return row


async def list_student_guardians(
    session: AsyncSession,
    ctx: TenantContext,
    student_id: UUID,
) -> list[StudentGuardian]:
    await get_student(session, ctx, student_id)
    result = await session.execute(
        select(StudentGuardian)
        .where(StudentGuardian.student_id == student_id, StudentGuardian.status == "active")
        .order_by(StudentGuardian.created_at.desc())
    )
    return list(result.scalars())


async def update_student_guardian(
    session: AsyncSession,
    ctx: TenantContext,
    link_id: UUID,
    *,
    fields: dict[str, Any],
    request_id: str | None,
) -> StudentGuardian:
    row = await session.get(StudentGuardian, link_id)
    if row is None:
        raise NotFoundError()
    for key, value in fields.items():
        if value is not None and hasattr(row, key):
            setattr(row, key, value)
    await session.flush()
    await _audit(
        session,
        ctx,
        action="student_guardian.updated",
        resource_type="student_guardian",
        resource_id=row.id,
        request_id=request_id,
        metadata={"fields": sorted(fields.keys())},
    )
    return row


async def create_enrollment(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    student_id: UUID,
    academic_year_id: UUID,
    class_id: UUID,
    section_id: UUID,
    starts_on: date,
    request_id: str | None,
) -> Enrollment:
    await _require_student_in_tenant(session, ctx, student_id)
    await _validate_enrollment_placement(
        session,
        ctx,
        academic_year_id=academic_year_id,
        class_id=class_id,
        section_id=section_id,
    )
    row = Enrollment(
        tenant_id=_tenant_id(ctx),
        student_id=student_id,
        academic_year_id=academic_year_id,
        class_id=class_id,
        section_id=section_id,
        starts_on=starts_on,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Enrollment could not be created") from exc
    await _audit(
        session,
        ctx,
        action="enrollment.created",
        resource_type="enrollment",
        resource_id=row.id,
        request_id=request_id,
        metadata={"student_id": str(student_id)},
    )
    await enqueue_outbox(
        session,
        topic="enrollment.created",
        idempotency_key=f"enrollment.created:{row.id}",
        tenant_id=ctx.tenant_id,
        correlation_id=request_id,
        payload={"enrollment_id": str(row.id), "student_id": str(student_id)},
    )
    return row


async def list_enrollments_for_student(
    session: AsyncSession,
    ctx: TenantContext,
    student_id: UUID,
) -> list[Enrollment]:
    await _require_student_in_tenant(session, ctx, student_id)
    result = await session.execute(
        select(Enrollment).where(Enrollment.student_id == student_id).order_by(Enrollment.starts_on.desc())
    )
    return list(result.scalars())


async def update_enrollment(
    session: AsyncSession,
    ctx: TenantContext,
    enrollment_id: UUID,
    *,
    fields: dict[str, Any],
    request_id: str | None,
) -> Enrollment:
    row = await _require_enrollment_in_tenant(session, ctx, enrollment_id)
    if not fields:
        raise ValidationFailed("No fields to update")
    class_id = fields.get("class_id", row.class_id)
    section_id = fields.get("section_id", row.section_id)
    if "class_id" in fields or "section_id" in fields:
        await _validate_enrollment_placement(
            session,
            ctx,
            academic_year_id=row.academic_year_id,
            class_id=class_id,
            section_id=section_id,
        )
    changed: dict[str, Any] = {}
    for key, value in fields.items():
        if value is not None and getattr(row, key) != value:
            changed[key] = value
            setattr(row, key, value)
    if not changed:
        return row
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Enrollment could not be updated") from exc
    await _audit(
        session,
        ctx,
        action="enrollment.updated",
        resource_type="enrollment",
        resource_id=row.id,
        request_id=request_id,
        metadata={"fields": sorted(changed.keys())},
    )
    return row


async def list_enrollments(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    student_id: UUID | None,
    status: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[Enrollment], str | None]:
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    stmt = select(Enrollment).order_by(Enrollment.starts_on.desc(), Enrollment.id.desc())
    if student_id is not None:
        await _require_student_in_tenant(session, ctx, student_id)
        stmt = stmt.where(Enrollment.student_id == student_id)
    if status:
        stmt = stmt.where(Enrollment.status == status)
    decoded = decode_cursor(cursor) if cursor else None
    if decoded:
        created_at, row_id = decoded
        stmt = stmt.where(
            or_(
                Enrollment.created_at < created_at,
                and_(Enrollment.created_at == created_at, Enrollment.id < row_id),
            )
        )
    stmt = stmt.limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(created_at=last.created_at, row_id=last.id)
        rows = rows[:limit]
    return rows, next_cursor


async def close_enrollment(
    session: AsyncSession,
    ctx: TenantContext,
    enrollment_id: UUID,
    *,
    ends_on: date,
    status: str,
    request_id: str | None,
) -> Enrollment:
    row = await _require_enrollment_in_tenant(session, ctx, enrollment_id)
    row.ends_on = ends_on
    row.status = status
    await session.flush()
    await _audit(
        session,
        ctx,
        action="enrollment.closed",
        resource_type="enrollment",
        resource_id=row.id,
        request_id=request_id,
        metadata={"status": status},
    )
    return row
