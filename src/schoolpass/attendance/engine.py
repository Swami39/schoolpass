from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.attendance.models import (
    AttendanceNonSchoolDay,
    AttendanceObservationProcessing,
    AttendancePolicy,
    AttendanceRecord,
    AttendanceSignal,
)
from schoolpass.attendance.rules import (
    DIRECTION_ENTRY,
    DIRECTION_EXIT,
    dedupe_key,
    entry_status_for_time,
    is_weekend,
    policy_covers_date,
    resolve_signal_direction,
    school_local_date,
    school_local_time,
)
from schoolpass.db.mixins import utcnow
from schoolpass.identity.models import Tenant
from schoolpass.observability.metrics import metrics
from schoolpass.people.models import Enrollment, Student
from schoolpass.rfid.models import RfidEvent, RfidObservation, RfidReader
from schoolpass.rfid.resolution import RESOLUTION_RESOLVED

REJECT_NOT_RESOLVED = "not_resolved"
REJECT_NO_STUDENT = "no_student"
REJECT_DIRECTION = "direction_unresolved"
REJECT_NO_POLICY = "no_policy"
REJECT_NON_SCHOOL = "non_school_day"
REJECT_NOT_ENROLLED = "not_enrolled"
REJECT_WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class ProcessResult:
    status: str
    signal_created: bool = False
    record_updated: bool = False
    deduplicated: bool = False


async def enqueue_observation_processing(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    observation_id: UUID,
) -> None:
    session.add(
        AttendanceObservationProcessing(
            tenant_id=tenant_id,
            rfid_observation_id=observation_id,
            status="pending",
            attempt_count=0,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    )
    await session.flush()


async def _load_observation_bundle(
    session: AsyncSession,
    tenant_id: UUID,
    observation_id: UUID,
) -> tuple[RfidObservation, RfidEvent, RfidReader] | None:
    stmt = (
        select(RfidObservation, RfidEvent, RfidReader)
        .join(RfidEvent, RfidEvent.id == RfidObservation.rfid_event_id)
        .join(RfidReader, RfidReader.id == RfidEvent.reader_id)
        .where(
            RfidObservation.id == observation_id,
            RfidObservation.tenant_id == tenant_id,
        )
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return None
    return row[0], row[1], row[2]


async def _policy_for_date(session: AsyncSession, tenant_id: UUID, on_date: date) -> AttendancePolicy | None:
    result = await session.execute(
        select(AttendancePolicy)
        .where(AttendancePolicy.tenant_id == tenant_id)
        .order_by(AttendancePolicy.effective_from.desc())
    )
    for policy in result.scalars():
        if policy_covers_date(policy, on_date):
            return policy
    return None


async def _is_non_school_day(session: AsyncSession, tenant_id: UUID, on_date: date) -> bool:
    if is_weekend(on_date):
        return True
    row = await session.execute(
        select(AttendanceNonSchoolDay.id).where(
            AttendanceNonSchoolDay.tenant_id == tenant_id,
            AttendanceNonSchoolDay.on_date == on_date,
        )
    )
    return row.scalar_one_or_none() is not None


async def _enrollment_on_date(
    session: AsyncSession,
    tenant_id: UUID,
    student_id: UUID,
    on_date: date,
) -> Enrollment | None:
    stmt = (
        select(Enrollment)
        .where(
            Enrollment.tenant_id == tenant_id,
            Enrollment.student_id == student_id,
            Enrollment.starts_on <= on_date,
            Enrollment.status.in_(("active", "completed")),
        )
        .order_by(Enrollment.starts_on.desc())
    )
    for enrollment in (await session.execute(stmt)).scalars():
        if enrollment.ends_on is not None and enrollment.ends_on < on_date:
            continue
        if enrollment.status == "withdrawn":
            continue
        return enrollment
    return None


async def _get_or_create_record(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    student_id: UUID,
    attendance_date: date,
    academic_year_id: UUID | None,
) -> AttendanceRecord:
    existing = await session.execute(
        select(AttendanceRecord)
        .where(
            AttendanceRecord.tenant_id == tenant_id,
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.attendance_date == attendance_date,
        )
        .with_for_update()
    )
    record = existing.scalar_one_or_none()
    if record is not None:
        return record
    record = AttendanceRecord(
        tenant_id=tenant_id,
        student_id=student_id,
        academic_year_id=academic_year_id,
        attendance_date=attendance_date,
        status="present",
        source="rfid",
        version=1,
    )
    session.add(record)
    await session.flush()
    metrics.increment("attendance_records_created_total")
    return record


async def process_observation(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    observation_id: UUID,
) -> ProcessResult:
    bundle = await _load_observation_bundle(session, tenant_id, observation_id)
    if bundle is None:
        return ProcessResult(status="missing")
    observation, event, reader = bundle

    if observation.resolution_status != RESOLUTION_RESOLVED or observation.student_id is None:
        return ProcessResult(status="rejected")

    student = await session.get(Student, observation.student_id)
    if student is None or student.status == "withdrawn":
        return ProcessResult(status="rejected")

    tenant = await session.get(Tenant, tenant_id)
    timezone_name = tenant.timezone if tenant else "Asia/Kolkata"

    direction = resolve_signal_direction(
        reader_direction_mode=reader.direction_mode,
        event_direction=event.direction,
    )
    if direction is None:
        return ProcessResult(status="rejected")

    attendance_date = school_local_date(observation.observed_at, timezone_name)
    if await _is_non_school_day(session, tenant_id, attendance_date):
        return ProcessResult(status="rejected")

    policy = await _policy_for_date(session, tenant_id, attendance_date)
    if policy is None:
        return ProcessResult(status="rejected")

    enrollment = await _enrollment_on_date(session, tenant_id, observation.student_id, attendance_date)
    if enrollment is None:
        return ProcessResult(status="rejected")

    dedupe_seconds = (
        policy.entry_dedupe_seconds if direction == DIRECTION_ENTRY else policy.exit_dedupe_seconds
    )
    key = dedupe_key(
        student_id=str(observation.student_id),
        attendance_date=attendance_date,
        direction=direction,
        observed_at=observation.observed_at,
        dedupe_seconds=dedupe_seconds,
    )

    signal = AttendanceSignal(
        tenant_id=tenant_id,
        student_id=observation.student_id,
        rfid_observation_id=observation.id,
        attendance_date=attendance_date,
        direction=direction,
        observed_at=observation.observed_at,
        dedupe_key=key,
        created_at=utcnow(),
    )
    try:
        async with session.begin_nested():
            session.add(signal)
            await session.flush()
        metrics.increment("attendance_signals_created_total", direction=direction)
        signal_created = True
    except IntegrityError:
        existing_signal = await session.execute(
            select(AttendanceSignal).where(
                AttendanceSignal.tenant_id == tenant_id,
                AttendanceSignal.rfid_observation_id == observation.id,
            )
        )
        if existing_signal.scalar_one_or_none() is not None:
            return ProcessResult(status="processed", deduplicated=True)
        metrics.increment("attendance_signals_deduplicated_total", direction=direction)
        return ProcessResult(status="processed", deduplicated=True)

    record = await _get_or_create_record(
        session,
        tenant_id=tenant_id,
        student_id=observation.student_id,
        attendance_date=attendance_date,
        academic_year_id=enrollment.academic_year_id,
    )
    updated = False
    if direction == DIRECTION_ENTRY:
        if record.entry_at is None or observation.observed_at < record.entry_at:
            record.entry_at = observation.observed_at
            record.first_observation_id = observation.id
            local_t = school_local_time(observation.observed_at, timezone_name)
            record.status = entry_status_for_time(policy, local_t)
            updated = True
    elif direction == DIRECTION_EXIT:
        if record.exit_at is None or observation.observed_at > record.exit_at:
            record.exit_at = observation.observed_at
            record.last_observation_id = observation.id
            updated = True
    if updated:
        record.updated_at = utcnow()
        metrics.increment("attendance_records_updated_total")
    return ProcessResult(status="processed", signal_created=signal_created, record_updated=updated)


async def process_pending_observations(session: AsyncSession, *, limit: int = 50) -> int:
    result = await session.execute(
        select(AttendanceObservationProcessing)
        .where(AttendanceObservationProcessing.status == "pending")
        .order_by(AttendanceObservationProcessing.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    rows = list(result.scalars())
    processed = 0
    for row in rows:
        row.status = "processing"
        row.attempt_count += 1
        row.updated_at = utcnow()
        try:
            outcome = await process_observation(
                session,
                tenant_id=row.tenant_id,
                observation_id=row.rfid_observation_id,
            )
            if outcome.status == "rejected":
                row.status = "rejected"
                row.last_error_code = "rejected"
            else:
                row.status = "processed"
            row.processed_at = utcnow()
            row.updated_at = utcnow()
            processed += 1
        except Exception as exc:  # noqa: BLE001
            row.status = "failed"
            row.last_error_code = type(exc).__name__
            row.last_error_message = str(exc)[:255]
            row.updated_at = utcnow()
            metrics.increment("attendance_processing_failures_total")
    return processed
