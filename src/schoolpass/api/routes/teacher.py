from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.adapters.blob import BlobStore
from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.db.session import apply_tenant_context
from schoolpass.teacher import attendance as teacher_att
from schoolpass.teacher import classes as teacher_classes
from schoolpass.teacher import devices as teacher_devices
from schoolpass.teacher import messages as teacher_messages
from schoolpass.teacher import nfc_sync as teacher_nfc
from schoolpass.teacher import profile as teacher_profile
from schoolpass.teacher import results as teacher_results
from schoolpass.teacher import timetable as teacher_timetable
from schoolpass.teacher.schemas import (
    AssessmentItem,
    AssessmentListResponse,
    AssessmentMarksResponse,
    StudentMarkItem,
    StudentMarkUpsertRequest,
    TeacherAttendanceItem,
    TeacherAttendanceListResponse,
    TeacherAttendanceMarkRequest,
    TeacherClassItem,
    TeacherClassListResponse,
    TeacherClientDeviceRegisterRequest,
    TeacherClientDeviceResponse,
    TeacherMeResponse,
    TeacherMessageRequest,
    TeacherMessageResponse,
    TeacherNfcSyncRequest,
    TeacherNfcSyncResponse,
    TeacherStudentItem,
    TeacherStudentListResponse,
    TimetableListResponse,
    TimetablePeriodItem,
    TimetablePeriodUpdate,
)
from schoolpass.tenancy.context import TenantContext

router = APIRouter(prefix="/api/v1/teacher", tags=["teacher"])


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def get_blob(request: Request) -> BlobStore:
    return cast(BlobStore, request.app.state.blob)


@router.get("/me", response_model=TeacherMeResponse)
async def teacher_me(
    principal: Annotated[Principal, Depends(require("teacher:me_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> TeacherMeResponse:
    async with factory() as session:
        await apply_tenant_context(session, _ctx(principal))
        row = await teacher_profile.get_teacher_me(session, _ctx(principal))
    return TeacherMeResponse.from_summary(row)


@router.get("/classes", response_model=TeacherClassListResponse)
async def list_classes(
    principal: Annotated[Principal, Depends(require("teacher:classes_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> TeacherClassListResponse:
    async with factory() as session:
        await apply_tenant_context(session, _ctx(principal))
        rows = await teacher_classes.list_teacher_classes(session, _ctx(principal))
    return TeacherClassListResponse(items=[TeacherClassItem.from_summary(r) for r in rows])


@router.get("/classes/{section_id}/students", response_model=TeacherStudentListResponse)
async def list_students(
    section_id: UUID,
    principal: Annotated[Principal, Depends(require("teacher:students_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> TeacherStudentListResponse:
    async with factory() as session:
        await apply_tenant_context(session, _ctx(principal))
        rows = await teacher_classes.list_section_students(session, _ctx(principal), section_id=section_id)
    return TeacherStudentListResponse(items=[TeacherStudentItem.from_summary(r) for r in rows])


@router.get("/classes/{section_id}/attendance", response_model=TeacherAttendanceListResponse)
async def list_attendance(
    section_id: UUID,
    principal: Annotated[Principal, Depends(require("teacher:attendance_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    date: str = Query(..., alias="date"),
) -> TeacherAttendanceListResponse:
    from datetime import date as date_cls

    on_date = date_cls.fromisoformat(date)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await teacher_att.list_section_attendance(
                session, _ctx(principal), section_id=section_id, on_date=on_date
            )
    return TeacherAttendanceListResponse(
        items=[
            TeacherAttendanceItem(
                id=r.id,
                student_id=r.student_id,
                attendance_date=r.attendance_date,
                status=r.status,
                entry_at=r.entry_at,
                exit_at=r.exit_at,
                source=r.source,
            )
            for r in rows
        ]
    )


@router.post("/classes/{section_id}/attendance", response_model=TeacherAttendanceItem)
async def mark_attendance(
    section_id: UUID,
    body: TeacherAttendanceMarkRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require("teacher:attendance_write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    date: str = Query(..., alias="date"),
) -> TeacherAttendanceItem:
    from datetime import date as date_cls

    on_date = date_cls.fromisoformat(date)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await teacher_att.mark_student_attendance(
                session,
                _ctx(principal),
                section_id=section_id,
                student_id=body.student_id,
                on_date=on_date,
                status=body.status,
                entry_at=body.entry_at,
                exit_at=body.exit_at,
                reason=body.reason,
                request_id=_request_id(request),
            )
    return TeacherAttendanceItem(
        id=row.id,
        student_id=row.student_id,
        attendance_date=row.attendance_date,
        status=row.status,
        entry_at=row.entry_at,
        exit_at=row.exit_at,
        source=row.source,
    )


@router.post("/nfc/events/sync", response_model=TeacherNfcSyncResponse)
async def sync_class_nfc(
    request: Request,
    body: TeacherNfcSyncRequest,
    principal: Annotated[Principal, Depends(require("teacher:nfc_attendance"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> TeacherNfcSyncResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            device_id = await teacher_nfc.get_client_device_for_request(
                session,
                header_value=request.headers.get(teacher_nfc.HEADER_CLIENT_DEVICE),
                user_id=principal.user.id,
            )
            result = await teacher_nfc.sync_teacher_class_nfc(
                session,
                _ctx(principal),
                client_device_id=device_id,
                client_event_id=body.client_event_id,
                section_id=body.section_id,
                card_uid=body.card_uid,
                occurred_at=body.occurred_at,
                device_sequence=body.device_sequence,
                request_id=_request_id(request),
            )
    return TeacherNfcSyncResponse(
        result=result.category.value,
        client_event_id=result.client_event_id,
        server_event_id=result.server_event_id,
        attendance_record_id=result.attendance_record_id,
        occurred_at=result.occurred_at,
        received_at=result.received_at,
        rejection_code=result.rejection_code,
    )


@router.get("/timetable", response_model=TimetableListResponse)
async def list_timetable(
    principal: Annotated[Principal, Depends(require("teacher:timetable_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    academic_year_id: UUID | None = None,
) -> TimetableListResponse:
    async with factory() as session:
        await apply_tenant_context(session, _ctx(principal))
        rows = await teacher_timetable.list_teacher_timetable(
            session, _ctx(principal), academic_year_id=academic_year_id
        )
    return TimetableListResponse(items=[TimetablePeriodItem.from_row(r) for r in rows])


@router.patch("/timetable/{period_id}", response_model=TimetablePeriodItem)
async def patch_timetable_period(
    period_id: UUID,
    body: TimetablePeriodUpdate,
    principal: Annotated[Principal, Depends(require("teacher:timetable_write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> TimetablePeriodItem:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            period = await teacher_timetable.update_timetable_period(
                session,
                _ctx(principal),
                period_id=period_id,
                starts_at=body.starts_at,
                ends_at=body.ends_at,
                subject_id=body.subject_id,
                teacher_user_id=body.teacher_user_id,
            )
            rows = await teacher_timetable.list_teacher_timetable(session, _ctx(principal))
    match = next((r for r in rows if r.id == period.id), None)
    if match is None:
        raise RuntimeError("timetable period missing after update")
    return TimetablePeriodItem.from_row(match)


@router.get("/classes/{section_id}/assessments", response_model=AssessmentListResponse)
async def list_assessments(
    section_id: UUID,
    principal: Annotated[Principal, Depends(require("teacher:results_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    subject_id: UUID | None = None,
) -> AssessmentListResponse:
    async with factory() as session:
        await apply_tenant_context(session, _ctx(principal))
        rows = await teacher_results.list_assessments_for_section(
            session, _ctx(principal), section_id=section_id, subject_id=subject_id
        )
    return AssessmentListResponse(items=[AssessmentItem.from_summary(r) for r in rows])


@router.get("/assessments/{assessment_id}/marks", response_model=AssessmentMarksResponse)
async def get_assessment_marks(
    assessment_id: UUID,
    principal: Annotated[Principal, Depends(require("teacher:results_read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AssessmentMarksResponse:
    async with factory() as session:
        await apply_tenant_context(session, _ctx(principal))
        assessment, rows = await teacher_results.list_marks_for_assessment(
            session, _ctx(principal), assessment_id=assessment_id
        )
    return AssessmentMarksResponse(
        assessment_id=assessment.id,
        max_marks=assessment.max_marks,
        items=[StudentMarkItem.from_row(r) for r in rows],
    )


@router.put("/assessments/{assessment_id}/students/{student_id}/marks", response_model=StudentMarkItem)
async def upsert_mark(
    assessment_id: UUID,
    student_id: UUID,
    body: StudentMarkUpsertRequest,
    principal: Annotated[Principal, Depends(require("teacher:results_write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> StudentMarkItem:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await teacher_results.upsert_student_mark(
                session,
                _ctx(principal),
                assessment_id=assessment_id,
                student_id=student_id,
                marks=body.marks,
            )
    return StudentMarkItem(
        student_id=student_id,
        marks=row.marks,
        mark_id=row.id,
        version=row.version,
    )


@router.post("/messages", response_model=TeacherMessageResponse)
async def post_message(
    body: TeacherMessageRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require("teacher:messages_write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    blob: Annotated[BlobStore, Depends(get_blob)],
) -> TeacherMessageResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            result = await teacher_messages.send_teacher_message(
                session,
                _ctx(principal),
                section_id=body.section_id,
                student_id=body.student_id,
                title=body.title,
                body=body.body,
                urgent=body.urgent,
                idempotency_key=body.idempotency_key,
                image_bytes=None,
                image_mime=None,
                image_file_id=body.image_file_id,
                blob=blob,
                request_id=_request_id(request),
            )
    return TeacherMessageResponse(
        message_id=result.message_id,
        recipient_count=result.recipient_count,
        created=result.created,
    )


@router.post("/messages/with-image", response_model=TeacherMessageResponse)
async def post_message_with_image(
    request: Request,
    principal: Annotated[Principal, Depends(require("teacher:messages_write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    blob: Annotated[BlobStore, Depends(get_blob)],
    title: Annotated[str, Form()],
    body: Annotated[str, Form()],
    idempotency_key: Annotated[str, Form()],
    section_id: Annotated[UUID | None, Form()] = None,
    student_id: Annotated[UUID | None, Form()] = None,
    urgent: Annotated[bool, Form()] = False,
    image: Annotated[UploadFile | None, File()] = None,
) -> TeacherMessageResponse:
    image_bytes: bytes | None = None
    image_mime: str | None = None
    if image is not None:
        image_bytes = await image.read()
        image_mime = image.content_type
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            result = await teacher_messages.send_teacher_message(
                session,
                _ctx(principal),
                section_id=section_id,
                student_id=student_id,
                title=title,
                body=body,
                urgent=urgent,
                idempotency_key=idempotency_key,
                image_bytes=image_bytes,
                image_mime=image_mime,
                image_file_id=None,
                blob=blob,
                request_id=_request_id(request),
            )
    return TeacherMessageResponse(
        message_id=result.message_id,
        recipient_count=result.recipient_count,
        created=result.created,
    )


@router.post("/client-devices", response_model=TeacherClientDeviceResponse)
async def register_client_device(
    body: TeacherClientDeviceRegisterRequest,
    principal: Annotated[Principal, Depends(require("teacher:nfc_attendance"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> TeacherClientDeviceResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            device = await teacher_devices.register_teacher_client_device(
                session,
                _ctx(principal),
                device_uuid=body.device_uuid,
            )
    return TeacherClientDeviceResponse(client_device_id=device.id)
