from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.attendance.rules import DIRECTION_ENTRY, DIRECTION_EXIT
from schoolpass.identity.models import Tenant
from schoolpass.notifications.constants import (
    NOTIFICATION_TYPE_BUS_BOARDING,
    NOTIFICATION_TYPE_BUS_DROPOFF,
    NOTIFICATION_TYPE_SCHOOL_ENTRY,
    NOTIFICATION_TYPE_SCHOOL_EXIT,
)
from schoolpass.notifications.recipients import list_guardian_recipient_user_ids
from schoolpass.notifications.service import build_idempotency_key, create_notification_with_outbox
from schoolpass.notifications.templates import render_notification
from schoolpass.people.models import Student
from schoolpass.transport.models import TransportBoardingRecord, Trip

REFERENCE_ATTENDANCE_SIGNAL = "attendance_signal"
REFERENCE_TRANSPORT_BOARDING = "transport_boarding_record"


async def emit_attendance_signal_notifications(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    student_id: UUID,
    signal_id: UUID,
    direction: str,
    correlation_id: str | None = None,
) -> int:
    if direction == DIRECTION_ENTRY:
        notification_type = NOTIFICATION_TYPE_SCHOOL_ENTRY
    elif direction == DIRECTION_EXIT:
        notification_type = NOTIFICATION_TYPE_SCHOOL_EXIT
    else:
        return 0

    recipients = await list_guardian_recipient_user_ids(session, tenant_id=tenant_id, student_id=student_id)
    if not recipients:
        return 0

    student = await session.get(Student, student_id)
    tenant = await session.get(Tenant, tenant_id)
    school_name = tenant.legal_name if tenant else "School"
    student_name = None
    if student is not None and student.pii_state == "active":
        student_name = f"{student.first_name} {student.last_name}".strip()

    rendered = render_notification(
        notification_type,
        student_display_name=student_name,
        school_display_name=school_name,
    )
    created = 0
    for recipient_user_id in recipients:
        idem = build_idempotency_key(
            notification_type=notification_type,
            reference_id=signal_id,
            recipient_user_id=recipient_user_id,
        )
        await create_notification_with_outbox(
            session,
            tenant_id=tenant_id,
            recipient_user_id=recipient_user_id,
            notification_type=notification_type,
            title=rendered.title,
            body=rendered.body,
            payload={
                "student_id": str(student_id),
                "reference_type": REFERENCE_ATTENDANCE_SIGNAL,
                "reference_id": str(signal_id),
            },
            idempotency_key=idem,
            correlation_id=correlation_id,
            reference_type=REFERENCE_ATTENDANCE_SIGNAL,
            reference_id=signal_id,
        )
        created += 1
    return created


async def emit_transport_boarding_notifications(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    boarding: TransportBoardingRecord,
    correlation_id: str | None = None,
) -> int:
    if boarding.event_type == "boarding":
        notification_type = NOTIFICATION_TYPE_BUS_BOARDING
    elif boarding.event_type == "dropoff":
        notification_type = NOTIFICATION_TYPE_BUS_DROPOFF
    else:
        return 0

    recipients = await list_guardian_recipient_user_ids(
        session, tenant_id=tenant_id, student_id=boarding.student_id
    )
    if not recipients:
        return 0

    student = await session.get(Student, boarding.student_id)
    tenant = await session.get(Tenant, tenant_id)
    trip = await session.get(Trip, boarding.trip_id)
    school_name = tenant.legal_name if tenant else "School"
    bus_name = None
    if trip is not None:
        bus_name = f"Trip {trip.id.hex[:8]}"
    student_name = None
    if student is not None and student.pii_state == "active":
        student_name = f"{student.first_name} {student.last_name}".strip()

    rendered = render_notification(
        notification_type,
        student_display_name=student_name,
        school_display_name=school_name,
        bus_display_name=bus_name,
    )
    created = 0
    for recipient_user_id in recipients:
        idem = build_idempotency_key(
            notification_type=notification_type,
            reference_id=boarding.id,
            recipient_user_id=recipient_user_id,
        )
        await create_notification_with_outbox(
            session,
            tenant_id=tenant_id,
            recipient_user_id=recipient_user_id,
            notification_type=notification_type,
            title=rendered.title,
            body=rendered.body,
            payload={
                "student_id": str(boarding.student_id),
                "reference_type": REFERENCE_TRANSPORT_BOARDING,
                "reference_id": str(boarding.id),
                "event_type": boarding.event_type,
            },
            idempotency_key=idem,
            correlation_id=correlation_id,
            reference_type=REFERENCE_TRANSPORT_BOARDING,
            reference_id=boarding.id,
        )
        created += 1
    return created
