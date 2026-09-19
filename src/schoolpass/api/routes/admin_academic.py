from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.admin import academic as admin_academic
from schoolpass.admin.academic_schemas import (
    AcademicYearCreateRequest,
    AcademicYearListResponse,
    AcademicYearResponse,
    AcademicYearUpdateRequest,
    SchoolClassCreateRequest,
    SchoolClassListResponse,
    SchoolClassResponse,
    SchoolClassUpdateRequest,
    SectionCreateRequest,
    SectionListResponse,
    SectionResponse,
    SectionUpdateRequest,
    SubjectCreateRequest,
    SubjectListResponse,
    SubjectResponse,
    SubjectUpdateRequest,
    TeacherAssignmentCreateRequest,
    TeacherAssignmentListResponse,
    TeacherAssignmentResponse,
    TeacherAssignmentUpdateRequest,
)
from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.api.routes.admin import _ctx, _request_id
from schoolpass.db.session import apply_tenant_context

router = APIRouter(prefix="/api/v1/admin", tags=["admin-academic"])


@router.get("/academic-years", response_model=AcademicYearListResponse)
async def list_academic_years(
    principal: Annotated[Principal, Depends(require("academic:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AcademicYearListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await admin_academic.list_academic_years(session, _ctx(principal))
    return AcademicYearListResponse(items=[AcademicYearResponse.model_validate(r) for r in rows])


@router.post("/academic-years", response_model=AcademicYearResponse)
async def create_academic_year(
    request: Request,
    body: AcademicYearCreateRequest,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AcademicYearResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_academic.create_academic_year(
                session, _ctx(principal), body, request_id=_request_id(request)
            )
    return AcademicYearResponse.model_validate(row)


@router.patch("/academic-years/{year_id}", response_model=AcademicYearResponse)
async def patch_academic_year(
    request: Request,
    year_id: UUID,
    body: AcademicYearUpdateRequest,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AcademicYearResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_academic.update_academic_year(
                session, _ctx(principal), year_id, body, request_id=_request_id(request)
            )
    return AcademicYearResponse.model_validate(row)


@router.get("/classes", response_model=SchoolClassListResponse)
async def list_classes(
    principal: Annotated[Principal, Depends(require("academic:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> SchoolClassListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await admin_academic.list_classes(session, _ctx(principal))
    return SchoolClassListResponse(items=[SchoolClassResponse.model_validate(r) for r in rows])


@router.post("/classes", response_model=SchoolClassResponse)
async def create_class(
    request: Request,
    body: SchoolClassCreateRequest,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> SchoolClassResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_academic.create_class(
                session, _ctx(principal), body, request_id=_request_id(request)
            )
    return SchoolClassResponse.model_validate(row)


@router.patch("/classes/{class_id}", response_model=SchoolClassResponse)
async def patch_class(
    request: Request,
    class_id: UUID,
    body: SchoolClassUpdateRequest,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> SchoolClassResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_academic.update_class(
                session, _ctx(principal), class_id, body, request_id=_request_id(request)
            )
    return SchoolClassResponse.model_validate(row)


@router.get("/sections", response_model=SectionListResponse)
async def list_sections(
    principal: Annotated[Principal, Depends(require("academic:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    class_id: UUID | None = None,
) -> SectionListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await admin_academic.list_sections(session, _ctx(principal), class_id=class_id)
    return SectionListResponse(items=[SectionResponse.model_validate(r) for r in rows])


@router.post("/sections", response_model=SectionResponse)
async def create_section(
    request: Request,
    body: SectionCreateRequest,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> SectionResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_academic.create_section(
                session, _ctx(principal), body, request_id=_request_id(request)
            )
    return SectionResponse.model_validate(row)


@router.patch("/sections/{section_id}", response_model=SectionResponse)
async def patch_section(
    request: Request,
    section_id: UUID,
    body: SectionUpdateRequest,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> SectionResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_academic.update_section(
                session, _ctx(principal), section_id, body, request_id=_request_id(request)
            )
    return SectionResponse.model_validate(row)


@router.get("/subjects", response_model=SubjectListResponse)
async def list_subjects(
    principal: Annotated[Principal, Depends(require("academic:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> SubjectListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await admin_academic.list_subjects(session, _ctx(principal))
    return SubjectListResponse(items=[SubjectResponse.model_validate(r) for r in rows])


@router.post("/subjects", response_model=SubjectResponse)
async def create_subject(
    request: Request,
    body: SubjectCreateRequest,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> SubjectResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_academic.create_subject(
                session, _ctx(principal), body, request_id=_request_id(request)
            )
    return SubjectResponse.model_validate(row)


@router.patch("/subjects/{subject_id}", response_model=SubjectResponse)
async def patch_subject(
    request: Request,
    subject_id: UUID,
    body: SubjectUpdateRequest,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> SubjectResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_academic.update_subject(
                session, _ctx(principal), subject_id, body, request_id=_request_id(request)
            )
    return SubjectResponse.model_validate(row)


@router.get("/teacher-assignments", response_model=TeacherAssignmentListResponse)
async def list_teacher_assignments(
    principal: Annotated[Principal, Depends(require("academic:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> TeacherAssignmentListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await admin_academic.list_teacher_assignments(session, _ctx(principal))
    return TeacherAssignmentListResponse(
        items=[TeacherAssignmentResponse.model_validate(r) for r in rows]
    )


@router.post("/teacher-assignments", response_model=TeacherAssignmentResponse)
async def create_teacher_assignment(
    request: Request,
    body: TeacherAssignmentCreateRequest,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> TeacherAssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_academic.create_teacher_assignment(
                session, _ctx(principal), body, request_id=_request_id(request)
            )
    return TeacherAssignmentResponse.model_validate(row)


@router.patch("/teacher-assignments/{assignment_id}", response_model=TeacherAssignmentResponse)
async def patch_teacher_assignment(
    request: Request,
    assignment_id: UUID,
    body: TeacherAssignmentUpdateRequest,
    principal: Annotated[Principal, Depends(require("academic:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> TeacherAssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await admin_academic.update_teacher_assignment(
                session, _ctx(principal), assignment_id, body, request_id=_request_id(request)
            )
    return TeacherAssignmentResponse.model_validate(row)
