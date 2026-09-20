from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.admin import people_schemas as ap
from schoolpass.admin import staff as admin_staff
from schoolpass.admin.people_support import validate_student_photo
from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.api.routes.admin import _ctx, _request_id
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import ValidationFailed
from schoolpass.people import services as svc
from schoolpass.people.pagination import decode_cursor

router = APIRouter(prefix="/api/v1/admin", tags=["admin-people"])


@router.get("/staff", response_model=ap.AdminStaffListResponse)
async def list_staff(
    principal: Annotated[Principal, Depends(require("people:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    staff_type: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> ap.AdminStaffListResponse:
    if cursor:
        try:
            decode_cursor(cursor)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await admin_staff.list_staff(
                session,
                _ctx(principal),
                staff_type=staff_type,
                search=search,
                limit=limit,
                cursor=cursor,
            )
    return ap.AdminStaffListResponse(
        items=[ap.AdminStaffResponse.from_row(staff, user) for staff, user in rows],
        next_cursor=next_cursor,
    )


@router.get("/staff/{staff_id}", response_model=ap.AdminStaffResponse)
async def get_staff_member(
    staff_id: UUID,
    principal: Annotated[Principal, Depends(require("people:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.AdminStaffResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_staff.get_staff(session, _ctx(principal), staff_id)
            from schoolpass.identity.models import User

            user = await session.get(User, row.user_id)
    return ap.AdminStaffResponse.from_row(row, user)


@router.post("/staff", response_model=ap.AdminStaffResponse)
async def create_staff_member(
    request: Request,
    body: ap.AdminStaffCreate,
    principal: Annotated[Principal, Depends(require("people:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.AdminStaffResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_staff.create_staff(
                session,
                _ctx(principal),
                user_id=body.user_id,
                staff_type=body.staff_type,
                employee_code=body.employee_code,
                request_id=_request_id(request),
            )
            from schoolpass.identity.models import User

            user = await session.get(User, row.user_id)
    return ap.AdminStaffResponse.from_row(row, user)


@router.patch("/staff/{staff_id}", response_model=ap.AdminStaffResponse)
async def patch_staff_member(
    request: Request,
    staff_id: UUID,
    body: ap.AdminStaffUpdate,
    principal: Annotated[Principal, Depends(require("people:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.AdminStaffResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_staff.update_staff(
                session,
                _ctx(principal),
                staff_id,
                fields=body.model_dump(exclude_unset=True),
                request_id=_request_id(request),
            )
            from schoolpass.identity.models import User

            user = await session.get(User, row.user_id)
    return ap.AdminStaffResponse.from_row(row, user)


@router.get("/students", response_model=ap.StudentListResponse)
async def list_students(
    principal: Annotated[Principal, Depends(require("people:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    status: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> ap.StudentListResponse:
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
                include_hidden=False,
                search=search,
                limit=limit,
                cursor=cursor,
            )
    return ap.StudentListResponse(
        items=[ap.StudentResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.post("/students", response_model=ap.StudentResponse)
async def create_student(
    request: Request,
    body: ap.AdminStudentCreate,
    principal: Annotated[Principal, Depends(require("people:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.StudentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            await validate_student_photo(session, _ctx(principal), body.photo_file_id)
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
    return ap.StudentResponse.model_validate(row, from_attributes=True)


@router.get("/students/{student_id}", response_model=ap.StudentResponse)
async def get_student(
    student_id: UUID,
    principal: Annotated[Principal, Depends(require("people:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.StudentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_student(session, _ctx(principal), student_id)
    return ap.StudentResponse.model_validate(row, from_attributes=True)


@router.patch("/students/{student_id}", response_model=ap.StudentResponse)
async def patch_student(
    request: Request,
    student_id: UUID,
    body: ap.AdminStudentUpdate,
    principal: Annotated[Principal, Depends(require("people:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.StudentResponse:
    fields = body.model_dump(exclude_unset=True)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            if "photo_file_id" in fields:
                await validate_student_photo(session, _ctx(principal), fields.get("photo_file_id"))
            row = await svc.update_student(
                session,
                _ctx(principal),
                student_id,
                fields=fields,
                request_id=_request_id(request),
            )
    return ap.StudentResponse.model_validate(row, from_attributes=True)


@router.get("/guardians", response_model=ap.GuardianListResponse)
async def list_guardians(
    principal: Annotated[Principal, Depends(require("people:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> ap.GuardianListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await svc.list_guardians(session, _ctx(principal), limit=limit, cursor=cursor)
    return ap.GuardianListResponse(
        items=[ap.GuardianResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.post("/guardians", response_model=ap.GuardianResponse)
async def create_guardian(
    request: Request,
    body: ap.AdminGuardianCreate,
    principal: Annotated[Principal, Depends(require("people:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.GuardianResponse:
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
                create_parent_login=body.create_parent_login,
            )
    return ap.GuardianResponse.model_validate(row, from_attributes=True)


@router.get("/guardians/{guardian_id}", response_model=ap.GuardianResponse)
async def get_guardian(
    guardian_id: UUID,
    principal: Annotated[Principal, Depends(require("people:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.GuardianResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_guardian(session, _ctx(principal), guardian_id)
    return ap.GuardianResponse.model_validate(row, from_attributes=True)


@router.patch("/guardians/{guardian_id}", response_model=ap.GuardianResponse)
async def patch_guardian(
    request: Request,
    guardian_id: UUID,
    body: ap.AdminGuardianUpdate,
    principal: Annotated[Principal, Depends(require("people:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.GuardianResponse:
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
    return ap.GuardianResponse.model_validate(row, from_attributes=True)


@router.get("/students/{student_id}/guardians", response_model=ap.StudentGuardianListResponse)
async def list_student_guardians(
    student_id: UUID,
    principal: Annotated[Principal, Depends(require("people:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.StudentGuardianListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await svc.list_student_guardians(session, _ctx(principal), student_id)
    return ap.StudentGuardianListResponse(
        items=[ap.StudentGuardianResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=None,
    )


@router.post("/students/{student_id}/guardians", response_model=ap.StudentGuardianResponse)
async def attach_student_guardian(
    request: Request,
    student_id: UUID,
    body: ap.AdminStudentGuardianCreate,
    principal: Annotated[Principal, Depends(require("people:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.StudentGuardianResponse:
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
    return ap.StudentGuardianResponse.model_validate(row, from_attributes=True)


@router.patch("/student-guardians/{link_id}", response_model=ap.StudentGuardianResponse)
async def patch_student_guardian(
    request: Request,
    link_id: UUID,
    body: ap.AdminStudentGuardianUpdate,
    principal: Annotated[Principal, Depends(require("people:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.StudentGuardianResponse:
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
    return ap.StudentGuardianResponse.model_validate(row, from_attributes=True)


@router.get("/enrollments", response_model=ap.EnrollmentListResponse)
async def list_enrollments(
    principal: Annotated[Principal, Depends(require("people:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    student_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> ap.EnrollmentListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await svc.list_enrollments(
                session,
                _ctx(principal),
                student_id=student_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
    return ap.EnrollmentListResponse(
        items=[ap.EnrollmentResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.post("/enrollments", response_model=ap.EnrollmentResponse)
async def create_enrollment(
    request: Request,
    body: ap.AdminEnrollmentCreate,
    principal: Annotated[Principal, Depends(require("people:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.EnrollmentResponse:
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
    return ap.EnrollmentResponse.model_validate(row, from_attributes=True)


@router.patch("/enrollments/{enrollment_id}", response_model=ap.EnrollmentResponse)
async def patch_enrollment(
    request: Request,
    enrollment_id: UUID,
    body: ap.AdminEnrollmentUpdate,
    principal: Annotated[Principal, Depends(require("people:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.EnrollmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.update_enrollment(
                session,
                _ctx(principal),
                enrollment_id,
                fields=body.model_dump(exclude_unset=True),
                request_id=_request_id(request),
            )
    return ap.EnrollmentResponse.model_validate(row, from_attributes=True)


@router.post("/enrollments/{enrollment_id}/close", response_model=ap.EnrollmentResponse)
async def close_enrollment(
    request: Request,
    enrollment_id: UUID,
    body: ap.AdminEnrollmentClose,
    principal: Annotated[Principal, Depends(require("people:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.EnrollmentResponse:
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
    return ap.EnrollmentResponse.model_validate(row, from_attributes=True)


@router.get("/students/{student_id}/enrollments", response_model=ap.EnrollmentListResponse)
async def list_student_enrollments(
    student_id: UUID,
    principal: Annotated[Principal, Depends(require("people:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ap.EnrollmentListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await svc.list_enrollments_for_student(session, _ctx(principal), student_id)
    return ap.EnrollmentListResponse(
        items=[ap.EnrollmentResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=None,
    )
