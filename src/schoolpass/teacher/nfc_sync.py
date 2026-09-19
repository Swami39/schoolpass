"""Teacher class NFC attendance fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.cards.normalize import normalize_hf_uid
from schoolpass.db.mixins import utcnow
from schoolpass.errors import AuthenticationError, NotFoundError
from schoolpass.identity.models import ClientDevice
from schoolpass.people.models import Enrollment
from schoolpass.rfid.resolution import (
    RESOLUTION_BLOCKED,
    RESOLUTION_RESOLVED,
    RESOLUTION_RETIRED,
    RESOLUTION_UNASSIGNED,
    resolve_card,
)
from schoolpass.teacher.access import assert_teacher_assigned_to_section, load_teacher_staff
from schoolpass.teacher.attendance import mark_student_attendance
from schoolpass.teacher.models import TeacherClassNfcEvent
from schoolpass.tenancy.context import TenantContext

HEADER_CLIENT_DEVICE = "x-client-device-id"


class TeacherNfcResultCategory(StrEnum):
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


@dataclass(frozen=True)
class TeacherNfcSyncResult:
    category: TeacherNfcResultCategory
    server_event_id: UUID
    client_event_id: UUID
    occurred_at: datetime
    received_at: datetime
    attendance_record_id: UUID | None
    rejection_code: str | None


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def get_client_device_for_request(
    session: AsyncSession,
    *,
    header_value: str | None,
    user_id: UUID,
) -> UUID:
    if not header_value:
        raise AuthenticationError("Client device header is required")
    try:
        device_id = UUID(header_value.strip())
    except ValueError:
        raise AuthenticationError("Invalid client device id") from None
    device = await session.get(ClientDevice, device_id)
    if device is None or device.user_id != user_id or device.status != "active":
        raise AuthenticationError("Invalid client device")
    return device_id


async def sync_teacher_class_nfc(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    client_device_id: UUID,
    client_event_id: UUID,
    section_id: UUID,
    card_uid: str,
    occurred_at: datetime,
    device_sequence: int | None,
    request_id: str | None,
) -> TeacherNfcSyncResult:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    tenant_id = ctx.tenant_id
    teacher_user_id = ctx.user_id
    occurred_at = _ensure_utc(occurred_at)
    received_at = utcnow()
    await load_teacher_staff(session, tenant_id=tenant_id, user_id=teacher_user_id)
    await assert_teacher_assigned_to_section(
        session,
        tenant_id=tenant_id,
        teacher_user_id=teacher_user_id,
        section_id=section_id,
    )
    existing = (
        await session.execute(
            select(TeacherClassNfcEvent).where(
                TeacherClassNfcEvent.client_device_id == client_device_id,
                TeacherClassNfcEvent.client_event_id == client_event_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return TeacherNfcSyncResult(
            category=TeacherNfcResultCategory.DUPLICATE,
            server_event_id=existing.id,
            client_event_id=client_event_id,
            occurred_at=existing.occurred_at,
            received_at=existing.received_at,
            attendance_record_id=existing.attendance_record_id,
            rejection_code=existing.rejection_code,
        )

    normalized_uid = normalize_hf_uid(card_uid)
    resolution = await resolve_card(
        session,
        tenant_id,
        hf_uid=normalized_uid,
        uhf_epc=None,
        uhf_tid=None,
        occurred_at=occurred_at,
    )
    processing_state = "rejected"
    rejection_code: str | None = None
    student_id: UUID | None = None
    attendance_record_id: UUID | None = None

    if resolution.resolution_status != RESOLUTION_RESOLVED or resolution.student_id is None:
        if resolution.resolution_status == RESOLUTION_BLOCKED:
            rejection_code = "card_blocked"
        elif resolution.resolution_status == RESOLUTION_RETIRED:
            rejection_code = "card_retired"
        elif resolution.resolution_status == RESOLUTION_UNASSIGNED:
            rejection_code = "card_unassigned"
        else:
            rejection_code = "unknown_card"
    else:
        student_id = resolution.student_id
        on_date = occurred_at.date()
        enrolled = (
            await session.execute(
                select(Enrollment.id).where(
                    Enrollment.tenant_id == tenant_id,
                    Enrollment.student_id == student_id,
                    Enrollment.section_id == section_id,
                    Enrollment.status == "active",
                    Enrollment.starts_on <= on_date,
                )
            )
        ).scalar_one_or_none()
        if enrolled is None:
            rejection_code = "wrong_class"
        else:
            record = await mark_student_attendance(
                session,
                ctx,
                section_id=section_id,
                student_id=student_id,
                on_date=on_date,
                status="present",
                entry_at=occurred_at,
                exit_at=None,
                reason="NFC class attendance",
                request_id=request_id,
            )
            record.source = "nfc_teacher"
            await session.flush()
            attendance_record_id = record.id
            processing_state = "processed"

    event = TeacherClassNfcEvent(
        tenant_id=tenant_id,
        client_device_id=client_device_id,
        client_event_id=client_event_id,
        teacher_user_id=teacher_user_id,
        section_id=section_id,
        card_hf_uid=normalized_uid,
        student_id=student_id,
        attendance_record_id=attendance_record_id,
        occurred_at=occurred_at,
        received_at=received_at,
        processing_state=processing_state,
        rejection_code=rejection_code,
        device_sequence=device_sequence,
    )
    try:
        session.add(event)
        await session.flush()
    except IntegrityError:
        dup = (
            await session.execute(
                select(TeacherClassNfcEvent).where(
                    TeacherClassNfcEvent.client_device_id == client_device_id,
                    TeacherClassNfcEvent.client_event_id == client_event_id,
                )
            )
        ).scalar_one()
        return TeacherNfcSyncResult(
            category=TeacherNfcResultCategory.DUPLICATE,
            server_event_id=dup.id,
            client_event_id=client_event_id,
            occurred_at=dup.occurred_at,
            received_at=dup.received_at,
            attendance_record_id=dup.attendance_record_id,
            rejection_code=dup.rejection_code,
        )

    category = (
        TeacherNfcResultCategory.PROCESSED
        if processing_state == "processed"
        else TeacherNfcResultCategory.REJECTED
    )
    return TeacherNfcSyncResult(
        category=category,
        server_event_id=event.id,
        client_event_id=client_event_id,
        occurred_at=occurred_at,
        received_at=received_at,
        attendance_record_id=attendance_record_id,
        rejection_code=rejection_code,
    )
