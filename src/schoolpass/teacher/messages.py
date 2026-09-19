"""Teacher messages to parents via notification outbox."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.adapters.blob import BlobStore
from schoolpass.errors import NotFoundError, ValidationFailed
from schoolpass.notifications.constants import NOTIFICATION_TYPE_TEACHER_MESSAGE
from schoolpass.notifications.service import build_idempotency_key, create_notification_with_outbox
from schoolpass.people.models import Enrollment, FileMetadata, Guardian, Student, StudentGuardian
from schoolpass.teacher.access import (
    assert_student_in_teacher_section,
    assert_teacher_assigned_to_section,
    load_teacher_staff,
)
from schoolpass.teacher.models import TeacherMessage
from schoolpass.tenancy.context import TenantContext

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_MIME = frozenset({"image/jpeg", "image/png", "image/webp"})


@dataclass(frozen=True)
class TeacherMessageResult:
    message_id: UUID
    recipient_count: int
    created: bool


async def _resolve_teacher_message_image(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    teacher_user_id: UUID,
    image_file_id: UUID,
) -> UUID:
    row = await session.get(FileMetadata, image_file_id)
    if (
        row is None
        or row.tenant_id != tenant_id
        or row.status != "active"
        or row.purpose != "teacher_message_image"
        or row.created_by != teacher_user_id
    ):
        raise NotFoundError()
    return row.id


async def store_teacher_message_image(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    image_bytes: bytes,
    image_mime: str,
    blob: BlobStore,
) -> UUID:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    tenant_id = ctx.tenant_id
    await load_teacher_staff(session, tenant_id=tenant_id, user_id=ctx.user_id)
    if image_mime not in ALLOWED_IMAGE_MIME:
        raise ValidationFailed("Unsupported image type")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValidationFailed("Image too large")
    digest = hashlib.sha256(image_bytes).hexdigest()
    ext = "jpg" if image_mime == "image/jpeg" else "png" if image_mime == "image/png" else "webp"
    blob_key = f"{tenant_id}/teacher-messages/{uuid4()}.{ext}"
    await blob.put(blob_key, image_bytes, content_type=image_mime)
    file_row = FileMetadata(
        tenant_id=tenant_id,
        purpose="teacher_message_image",
        blob_key=blob_key,
        sha256=digest,
        classification="SENSITIVE_CHILD_DATA",
        created_by=ctx.user_id,
    )
    session.add(file_row)
    await session.flush()
    return file_row.id


async def _guardian_user_ids_for_student(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    student_id: UUID,
) -> list[UUID]:
    rows = (
        await session.execute(
            select(Guardian.user_id)
            .join(
                StudentGuardian,
                (StudentGuardian.guardian_id == Guardian.id) & (StudentGuardian.tenant_id == Guardian.tenant_id),
            )
            .where(
                StudentGuardian.tenant_id == tenant_id,
                StudentGuardian.student_id == student_id,
                StudentGuardian.status == "active",
                StudentGuardian.can_receive_notifications.is_(True),
                Guardian.status == "active",
                Guardian.user_id.is_not(None),
            )
        )
    ).scalars().all()
    return [uid for uid in rows if uid is not None]


async def send_teacher_message(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    section_id: UUID | None,
    student_id: UUID | None,
    title: str,
    body: str,
    urgent: bool,
    idempotency_key: str,
    image_bytes: bytes | None,
    image_mime: str | None,
    image_file_id: UUID | None,
    blob: BlobStore,
    request_id: str | None,
) -> TeacherMessageResult:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    tenant_id = ctx.tenant_id
    await load_teacher_staff(session, tenant_id=tenant_id, user_id=ctx.user_id)
    if not title.strip() or not body.strip():
        raise ValidationFailed("Title and body are required")
    if student_id is None and section_id is None:
        raise ValidationFailed("student_id or section_id is required")
    target_students: list[UUID] = []
    if student_id is not None:
        if section_id is None:
            raise ValidationFailed("section_id is required with student_id")
        await assert_student_in_teacher_section(
            session,
            tenant_id=tenant_id,
            teacher_user_id=ctx.user_id,
            section_id=section_id,
            student_id=student_id,
        )
        target_students = [student_id]
    else:
        assert section_id is not None
        await assert_teacher_assigned_to_section(
            session,
            tenant_id=tenant_id,
            teacher_user_id=ctx.user_id,
            section_id=section_id,
        )
        target_students = list(
            (
                await session.execute(
                    select(Enrollment.student_id).where(
                        Enrollment.tenant_id == tenant_id,
                        Enrollment.section_id == section_id,
                        Enrollment.status == "active",
                    )
                )
            ).scalars()
        )

    resolved_image_file_id: UUID | None = None
    if image_file_id is not None:
        resolved_image_file_id = await _resolve_teacher_message_image(
            session,
            tenant_id=tenant_id,
            teacher_user_id=ctx.user_id,
            image_file_id=image_file_id,
        )
    elif image_bytes is not None and image_mime is not None:
        resolved_image_file_id = await store_teacher_message_image(
            session,
            ctx,
            image_bytes=image_bytes,
            image_mime=image_mime,
            blob=blob,
        )

    existing = (
        await session.execute(
            select(TeacherMessage).where(
                TeacherMessage.tenant_id == tenant_id,
                TeacherMessage.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return TeacherMessageResult(message_id=existing.id, recipient_count=0, created=False)

    message = TeacherMessage(
        tenant_id=tenant_id,
        teacher_user_id=ctx.user_id,
        section_id=section_id,
        student_id=student_id,
        title=title.strip(),
        body=body.strip(),
        urgent=urgent,
        image_file_id=resolved_image_file_id,
        idempotency_key=idempotency_key,
    )
    try:
        session.add(message)
        await session.flush()
    except IntegrityError:
        dup = (
            await session.execute(
                select(TeacherMessage).where(
                    TeacherMessage.tenant_id == tenant_id,
                    TeacherMessage.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one()
        return TeacherMessageResult(message_id=dup.id, recipient_count=0, created=False)

    recipient_count = 0
    for sid in target_students:
        student = await session.get(Student, sid)
        if student is None or student.status != "active":
            continue
        for guardian_user_id in await _guardian_user_ids_for_student(
            session, tenant_id=tenant_id, student_id=sid
        ):
            notif_idem = build_idempotency_key(
                notification_type=NOTIFICATION_TYPE_TEACHER_MESSAGE,
                reference_id=message.id,
                recipient_user_id=guardian_user_id,
            )
            payload = {
                "student_id": str(sid),
                "teacher_message_id": str(message.id),
                "urgent": urgent,
            }
            if resolved_image_file_id is not None:
                payload["image_file_id"] = str(resolved_image_file_id)
            await create_notification_with_outbox(
                session,
                tenant_id=tenant_id,
                recipient_user_id=guardian_user_id,
                notification_type=NOTIFICATION_TYPE_TEACHER_MESSAGE,
                title=title.strip(),
                body=body.strip(),
                payload=payload,
                idempotency_key=notif_idem,
                correlation_id=request_id,
                reference_type="teacher_message",
                reference_id=message.id,
            )
            recipient_count += 1

    return TeacherMessageResult(message_id=message.id, recipient_count=recipient_count, created=True)
