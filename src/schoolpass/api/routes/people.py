from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import ValidationFailed
from schoolpass.people import schemas as s
from schoolpass.people import services as svc
from schoolpass.people.models import AcademicYear, SchoolClass, Section
from schoolpass.people.pagination import decode_cursor
from schoolpass.tenancy.context import TenantContext

router = APIRouter(prefix="/api/v1", tags=["people"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


@router.post("/students", response_model=s.StudentResponse)
async def create_student(
    body: s.StudentCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("students:create"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.StudentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.create_student(
                session,
                _ctx(principal),
                admission_no=body.admission_no,
                first_name=body.first_name,
                middle_name=body.middle_name,
                last_name=body.last_name,
                date_of_birth=body.date_of_birth,
                photo_file_id=body.photo_file_id,
                request_id=_request_id(request),
            )
    return s.StudentResponse.model_validate(row, from_attributes=True)


@router.get("/students/{student_id}", response_model=s.StudentResponse)
async def get_student(
    student_id: UUID,
    principal: Annotated[Principal, Depends(require("students:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.StudentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_student(session, _ctx(principal), student_id)
    return s.StudentResponse.model_validate(row, from_attributes=True)


@router.get("/students", response_model=s.StudentListResponse)
async def list_students(
    principal: Annotated[Principal, Depends(require("students:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    status: str | None = None,
    include_hidden: bool = False,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> s.StudentListResponse:
    if cursor:
        try:
            decode_cursor(cursor)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await svc.list_students(
                session,
                _ctx(principal),
                status=status,
                include_hidden=include_hidden,
                search=search,
                limit=limit,
                cursor=cursor,
            )
    return s.StudentListResponse(
        items=[s.StudentResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.patch("/students/{student_id}", response_model=s.StudentResponse)
async def update_student(
    student_id: UUID,
    body: s.StudentUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require("students:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.StudentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.update_student(
                session,
                _ctx(principal),
                student_id,
                fields=body.model_dump(exclude_unset=True),
                request_id=_request_id(request),
            )
    return s.StudentResponse.model_validate(row, from_attributes=True)


@router.post("/students/{student_id}/withdraw", response_model=s.StudentResponse)
async def withdraw_student(
    student_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("students:withdraw"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.StudentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.withdraw_student(session, _ctx(principal), student_id, request_id=_request_id(request))
    return s.StudentResponse.model_validate(row, from_attributes=True)


@router.post("/students/{student_id}/hide", response_model=s.StudentResponse)
async def hide_student(
    student_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("students:hide"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.StudentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.hide_student(session, _ctx(principal), student_id, request_id=_request_id(request))
    return s.StudentResponse.model_validate(row, from_attributes=True)


@router.post("/students/{student_id}/anonymize", response_model=s.StudentResponse)
async def anonymize_student(
    student_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("students:anonymize"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.StudentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.anonymize_student(session, _ctx(principal), student_id, request_id=_request_id(request))
    return s.StudentResponse.model_validate(row, from_attributes=True)


@router.post("/guardians", response_model=s.GuardianResponse)
async def create_guardian(
    body: s.GuardianCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("guardians:create"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.GuardianResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.create_guardian(
                session,
                _ctx(principal),
                first_name=body.first_name,
                last_name=body.last_name,
                phone_e164=body.phone_e164,
                email=body.email,
                request_id=_request_id(request),
            )
    return s.GuardianResponse.model_validate(row, from_attributes=True)


@router.get("/guardians/{guardian_id}", response_model=s.GuardianResponse)
async def get_guardian(
    guardian_id: UUID,
    principal: Annotated[Principal, Depends(require("guardians:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.GuardianResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_guardian(session, _ctx(principal), guardian_id)
    return s.GuardianResponse.model_validate(row, from_attributes=True)


@router.get("/guardians", response_model=s.GuardianListResponse)
async def list_guardians(
    principal: Annotated[Principal, Depends(require("guardians:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> s.GuardianListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await svc.list_guardians(session, _ctx(principal), limit=limit, cursor=cursor)
    return s.GuardianListResponse(
        items=[s.GuardianResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.patch("/guardians/{guardian_id}", response_model=s.GuardianResponse)
async def patch_guardian(
    guardian_id: UUID,
    body: s.GuardianUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require("guardians:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.GuardianResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.update_guardian(
                session,
                _ctx(principal),
                guardian_id,
                fields=body.model_dump(exclude_unset=True),
                request_id=_request_id(request),
            )
    return s.GuardianResponse.model_validate(row, from_attributes=True)


@router.post("/students/{student_id}/guardians", response_model=s.StudentGuardianResponse)
async def attach_guardian(
    student_id: UUID,
    body: s.StudentGuardianCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("student_guardians:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.StudentGuardianResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.attach_guardian(
                session,
                _ctx(principal),
                student_id=student_id,
                guardian_id=body.guardian_id,
                relationship_type=body.relationship_type,
                is_primary_contact=body.is_primary_contact,
                can_receive_notifications=body.can_receive_notifications,
                can_pay_fees=body.can_pay_fees,
                request_id=_request_id(request),
            )
    return s.StudentGuardianResponse.model_validate(row, from_attributes=True)


@router.get("/students/{student_id}/guardians", response_model=s.StudentGuardianListResponse)
async def list_student_guardians(
    student_id: UUID,
    principal: Annotated[Principal, Depends(require("student_guardians:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.StudentGuardianListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await svc.list_student_guardians(session, _ctx(principal), student_id)
    return s.StudentGuardianListResponse(
        items=[s.StudentGuardianResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=None,
    )


@router.get("/guardians/{guardian_id}/students", response_model=s.StudentGuardianListResponse)
async def list_guardian_students(
    guardian_id: UUID,
    principal: Annotated[Principal, Depends(require("student_guardians:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.StudentGuardianListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await svc.list_guardian_students(session, _ctx(principal), guardian_id)
    return s.StudentGuardianListResponse(
        items=[s.StudentGuardianResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=None,
    )


@router.patch("/student-guardians/{link_id}", response_model=s.StudentGuardianResponse)
async def patch_student_guardian(
    link_id: UUID,
    body: s.StudentGuardianUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require("student_guardians:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.StudentGuardianResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.update_student_guardian(
                session,
                _ctx(principal),
                link_id,
                fields=body.model_dump(exclude_unset=True),
                request_id=_request_id(request),
            )
    return s.StudentGuardianResponse.model_validate(row, from_attributes=True)


@router.post("/enrollments", response_model=s.EnrollmentResponse)
async def create_enrollment(
    body: s.EnrollmentCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("enrollments:create"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.EnrollmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.create_enrollment(
                session,
                _ctx(principal),
                student_id=body.student_id,
                academic_year_id=body.academic_year_id,
                class_id=body.class_id,
                section_id=body.section_id,
                starts_on=body.starts_on,
                request_id=_request_id(request),
            )
    return s.EnrollmentResponse.model_validate(row, from_attributes=True)


@router.get("/students/{student_id}/enrollments", response_model=s.EnrollmentListResponse)
async def list_enrollments(
    student_id: UUID,
    principal: Annotated[Principal, Depends(require("enrollments:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.EnrollmentListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await svc.list_enrollments_for_student(session, _ctx(principal), student_id)
    return s.EnrollmentListResponse(
        items=[s.EnrollmentResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=None,
    )


@router.post("/enrollments/{enrollment_id}/close", response_model=s.EnrollmentResponse)
async def close_enrollment(
    enrollment_id: UUID,
    body: s.EnrollmentClose,
    request: Request,
    principal: Annotated[Principal, Depends(require("enrollments:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.EnrollmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.close_enrollment(
                session,
                _ctx(principal),
                enrollment_id,
                ends_on=body.ends_on,
                status=body.status,
                request_id=_request_id(request),
            )
    return s.EnrollmentResponse.model_validate(row, from_attributes=True)


@router.post("/academic/years", response_model=dict[str, str])
async def create_academic_year(
    body: s.AcademicYearCreate,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> dict[str, str]:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            if principal.tenant_id is None:
                raise ValidationFailed("Tenant membership is required")
            row = AcademicYear(
                tenant_id=principal.tenant_id,
                code=body.code,
                name=body.name,
                starts_on=body.starts_on,
                ends_on=body.ends_on,
            )
            session.add(row)
            await session.flush()
    return {"id": str(row.id), "code": row.code}


@router.post("/academic/classes", response_model=dict[str, str])
async def create_class(
    body: s.SchoolClassCreate,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> dict[str, str]:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            if principal.tenant_id is None:
                raise ValidationFailed("Tenant membership is required")
            row = SchoolClass(
                tenant_id=principal.tenant_id,
                code=body.code,
                name=body.name,
            )
            session.add(row)
            await session.flush()
    return {"id": str(row.id), "code": row.code}


@router.post("/academic/sections", response_model=dict[str, str])
async def create_section(
    body: s.SectionCreate,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> dict[str, str]:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            if principal.tenant_id is None:
                raise ValidationFailed("Tenant membership is required")
            row = Section(
                tenant_id=principal.tenant_id,
                class_id=body.class_id,
                name=body.name,
            )
            session.add(row)
            await session.flush()
    return {"id": str(row.id), "name": row.name}
