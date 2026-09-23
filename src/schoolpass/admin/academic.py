from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.admin.academic_schemas import (
    AcademicYearCreateRequest,
    AcademicYearUpdateRequest,
    SchoolClassCreateRequest,
    SchoolClassUpdateRequest,
    SectionCreateRequest,
    SectionUpdateRequest,
    SubjectCreateRequest,
    SubjectUpdateRequest,
    TeacherAssignmentCreateRequest,
    TeacherAssignmentUpdateRequest,
)
from schoolpass.audit.service import record_audit
from schoolpass.errors import ConflictError, NotFoundError, ValidationFailed
from schoolpass.identity.models import StaffProfile
from schoolpass.people.models import AcademicYear, SchoolClass, Section
from schoolpass.teacher.models import Subject, TeacherSectionAssignment
from schoolpass.tenancy.context import TenantContext


def _tenant_id(ctx: TenantContext) -> UUID:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    return ctx.tenant_id


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


def _apply_patch(row: Any, updates: dict[str, Any]) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for field, value in updates.items():
        if getattr(row, field) != value:
            changed[field] = value
            setattr(row, field, value)
    return changed


async def _get_year(session: AsyncSession, ctx: TenantContext, year_id: UUID) -> AcademicYear:
    row = await session.get(AcademicYear, year_id)
    if row is None or row.tenant_id != _tenant_id(ctx):
        raise NotFoundError()
    return row


async def _get_class(session: AsyncSession, ctx: TenantContext, class_id: UUID) -> SchoolClass:
    row = await session.get(SchoolClass, class_id)
    if row is None or row.tenant_id != _tenant_id(ctx):
        raise NotFoundError()
    return row


async def _get_section(session: AsyncSession, ctx: TenantContext, section_id: UUID) -> Section:
    row = await session.get(Section, section_id)
    if row is None or row.tenant_id != _tenant_id(ctx):
        raise NotFoundError()
    return row


async def _get_subject(session: AsyncSession, ctx: TenantContext, subject_id: UUID) -> Subject:
    row = await session.get(Subject, subject_id)
    if row is None or row.tenant_id != _tenant_id(ctx):
        raise NotFoundError()
    return row


async def _assert_teacher_staff(session: AsyncSession, ctx: TenantContext, teacher_user_id: UUID) -> None:
    result = await session.execute(
        select(StaffProfile).where(
            StaffProfile.tenant_id == _tenant_id(ctx),
            StaffProfile.user_id == teacher_user_id,
            StaffProfile.staff_type == "teacher",
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValidationFailed("Teacher staff profile not found for this school")


async def _validate_assignment_refs(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    academic_year_id: UUID,
    section_id: UUID,
    subject_id: UUID | None,
    assignment_role: str,
) -> None:
    await _get_year(session, ctx, academic_year_id)
    await _get_section(session, ctx, section_id)
    if assignment_role == "subject_teacher" and subject_id is None:
        raise ValidationFailed("subject_id is required for subject_teacher assignments")
    if subject_id is not None:
        await _get_subject(session, ctx, subject_id)


async def list_academic_years(session: AsyncSession, ctx: TenantContext) -> list[AcademicYear]:
    tenant_id = _tenant_id(ctx)
    result = await session.execute(
        select(AcademicYear).where(AcademicYear.tenant_id == tenant_id).order_by(AcademicYear.starts_on.desc())
    )
    return list(result.scalars().all())


async def create_academic_year(
    session: AsyncSession,
    ctx: TenantContext,
    payload: AcademicYearCreateRequest,
    *,
    request_id: str | None,
) -> AcademicYear:
    row = AcademicYear(tenant_id=_tenant_id(ctx), **payload.model_dump())
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Academic year could not be created") from exc
    await _audit(
        session,
        ctx,
        action="academic_year.created",
        resource_type="academic_year",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def update_academic_year(
    session: AsyncSession,
    ctx: TenantContext,
    year_id: UUID,
    payload: AcademicYearUpdateRequest,
    *,
    request_id: str | None,
) -> AcademicYear:
    row = await _get_year(session, ctx, year_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise ValidationFailed("No fields to update")
    starts = updates.get("starts_on", row.starts_on)
    ends = updates.get("ends_on", row.ends_on)
    if ends < starts:
        raise ValidationFailed("ends_on must be on or after starts_on")
    changed = _apply_patch(row, updates)
    if not changed:
        return row
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Academic year could not be updated") from exc
    await _audit(
        session,
        ctx,
        action="academic_year.updated",
        resource_type="academic_year",
        resource_id=row.id,
        request_id=request_id,
        metadata={"fields": sorted(changed.keys())},
    )
    return row


async def list_classes(session: AsyncSession, ctx: TenantContext) -> list[SchoolClass]:
    tenant_id = _tenant_id(ctx)
    result = await session.execute(
        select(SchoolClass).where(SchoolClass.tenant_id == tenant_id).order_by(SchoolClass.name)
    )
    return list(result.scalars().all())


async def create_class(
    session: AsyncSession,
    ctx: TenantContext,
    payload: SchoolClassCreateRequest,
    *,
    request_id: str | None,
) -> SchoolClass:
    row = SchoolClass(tenant_id=_tenant_id(ctx), **payload.model_dump())
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Class could not be created") from exc
    await _audit(
        session,
        ctx,
        action="school_class.created",
        resource_type="school_class",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def update_class(
    session: AsyncSession,
    ctx: TenantContext,
    class_id: UUID,
    payload: SchoolClassUpdateRequest,
    *,
    request_id: str | None,
) -> SchoolClass:
    row = await _get_class(session, ctx, class_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise ValidationFailed("No fields to update")
    changed = _apply_patch(row, updates)
    if not changed:
        return row
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Class could not be updated") from exc
    await _audit(
        session,
        ctx,
        action="school_class.updated",
        resource_type="school_class",
        resource_id=row.id,
        request_id=request_id,
        metadata={"fields": sorted(changed.keys())},
    )
    return row


async def list_sections(
    session: AsyncSession, ctx: TenantContext, *, class_id: UUID | None = None
) -> list[Section]:
    tenant_id = _tenant_id(ctx)
    stmt = select(Section).where(Section.tenant_id == tenant_id)
    if class_id is not None:
        await _get_class(session, ctx, class_id)
        stmt = stmt.where(Section.class_id == class_id)
    result = await session.execute(stmt.order_by(Section.name))
    return list(result.scalars().all())


async def create_section(
    session: AsyncSession,
    ctx: TenantContext,
    payload: SectionCreateRequest,
    *,
    request_id: str | None,
) -> Section:
    await _get_class(session, ctx, payload.class_id)
    row = Section(tenant_id=_tenant_id(ctx), **payload.model_dump())
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Section could not be created") from exc
    await _audit(
        session,
        ctx,
        action="section.created",
        resource_type="section",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def update_section(
    session: AsyncSession,
    ctx: TenantContext,
    section_id: UUID,
    payload: SectionUpdateRequest,
    *,
    request_id: str | None,
) -> Section:
    row = await _get_section(session, ctx, section_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise ValidationFailed("No fields to update")
    changed = _apply_patch(row, updates)
    if not changed:
        return row
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Section could not be updated") from exc
    await _audit(
        session,
        ctx,
        action="section.updated",
        resource_type="section",
        resource_id=row.id,
        request_id=request_id,
        metadata={"fields": sorted(changed.keys())},
    )
    return row


async def list_subjects(session: AsyncSession, ctx: TenantContext) -> list[Subject]:
    tenant_id = _tenant_id(ctx)
    result = await session.execute(
        select(Subject).where(Subject.tenant_id == tenant_id).order_by(Subject.name)
    )
    return list(result.scalars().all())


async def create_subject(
    session: AsyncSession,
    ctx: TenantContext,
    payload: SubjectCreateRequest,
    *,
    request_id: str | None,
) -> Subject:
    row = Subject(tenant_id=_tenant_id(ctx), **payload.model_dump())
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Subject could not be created") from exc
    await _audit(
        session,
        ctx,
        action="subject.created",
        resource_type="subject",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def update_subject(
    session: AsyncSession,
    ctx: TenantContext,
    subject_id: UUID,
    payload: SubjectUpdateRequest,
    *,
    request_id: str | None,
) -> Subject:
    row = await _get_subject(session, ctx, subject_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise ValidationFailed("No fields to update")
    changed = _apply_patch(row, updates)
    if not changed:
        return row
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Subject could not be updated") from exc
    await _audit(
        session,
        ctx,
        action="subject.updated",
        resource_type="subject",
        resource_id=row.id,
        request_id=request_id,
        metadata={"fields": sorted(changed.keys())},
    )
    return row


async def list_teacher_assignments(
    session: AsyncSession, ctx: TenantContext, *, section_id: UUID | None = None
) -> list[TeacherSectionAssignment]:
    tenant_id = _tenant_id(ctx)
    stmt = select(TeacherSectionAssignment).where(TeacherSectionAssignment.tenant_id == tenant_id)
    if section_id is not None:
        await _get_section(session, ctx, section_id)
        stmt = stmt.where(TeacherSectionAssignment.section_id == section_id)
    result = await session.execute(stmt.order_by(TeacherSectionAssignment.created_at.desc()))
    return list(result.scalars().all())


async def create_teacher_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    payload: TeacherAssignmentCreateRequest,
    *,
    request_id: str | None,
) -> TeacherSectionAssignment:
    await _assert_teacher_staff(session, ctx, payload.teacher_user_id)
    await _validate_assignment_refs(
        session,
        ctx,
        academic_year_id=payload.academic_year_id,
        section_id=payload.section_id,
        subject_id=payload.subject_id,
        assignment_role=payload.assignment_role,
    )
    row = TeacherSectionAssignment(tenant_id=_tenant_id(ctx), **payload.model_dump())
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Teacher assignment could not be created") from exc
    await _audit(
        session,
        ctx,
        action="teacher_assignment.created",
        resource_type="teacher_section_assignment",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def update_teacher_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    assignment_id: UUID,
    payload: TeacherAssignmentUpdateRequest,
    *,
    request_id: str | None,
) -> TeacherSectionAssignment:
    row = await session.get(TeacherSectionAssignment, assignment_id)
    if row is None or row.tenant_id != _tenant_id(ctx):
        raise NotFoundError()
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise ValidationFailed("No fields to update")
    assignment_role = updates.get("assignment_role", row.assignment_role)
    subject_id = updates.get("subject_id", row.subject_id)
    if "subject_id" in updates or "assignment_role" in updates:
        await _validate_assignment_refs(
            session,
            ctx,
            academic_year_id=row.academic_year_id,
            section_id=row.section_id,
            subject_id=subject_id,
            assignment_role=assignment_role,
        )
    changed = _apply_patch(row, updates)
    if not changed:
        return row
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Teacher assignment could not be updated") from exc
    await _audit(
        session,
        ctx,
        action="teacher_assignment.updated",
        resource_type="teacher_section_assignment",
        resource_id=row.id,
        request_id=request_id,
        metadata={"fields": sorted(changed.keys())},
    )
    return row
