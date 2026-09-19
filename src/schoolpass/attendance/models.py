from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from schoolpass.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from schoolpass.db.session import Base


class AttendancePolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_policies"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    entry_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    present_until: Mapped[time | None] = mapped_column(Time, nullable=True)
    late_until: Mapped[time | None] = mapped_column(Time, nullable=True)
    entry_dedupe_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    exit_dedupe_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    __table_args__ = (UniqueConstraint("id", "tenant_id", name="uq_attendance_policies_id_tenant"),)


class AttendanceNonSchoolDay(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "attendance_non_school_days"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    on_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "on_date", name="uq_attendance_non_school_days_tenant_date"),
        UniqueConstraint("id", "tenant_id", name="uq_attendance_non_school_days_id_tenant"),
    )


class AttendanceSignal(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "attendance_signals"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    student_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    rfid_observation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_attendance_signals_student_tenant",
        ),
        ForeignKeyConstraint(
            ["rfid_observation_id", "tenant_id"],
            ["rfid_observations.id", "rfid_observations.tenant_id"],
            name="fk_attendance_signals_observation_tenant",
        ),
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_attendance_signals_dedupe"),
        UniqueConstraint("tenant_id", "rfid_observation_id", name="uq_attendance_signals_observation"),
        UniqueConstraint("id", "tenant_id", name="uq_attendance_signals_id_tenant"),
        CheckConstraint("direction IN ('entry', 'exit')", name="ck_attendance_signals_direction"),
    )


class AttendanceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_records"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    student_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    academic_year_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    entry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_observation_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    last_observation_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="rfid", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_attendance_records_student_tenant",
        ),
        ForeignKeyConstraint(
            ["academic_year_id", "tenant_id"],
            ["academic_years.id", "academic_years.tenant_id"],
            name="fk_attendance_records_year_tenant",
        ),
        UniqueConstraint("tenant_id", "student_id", "attendance_date", name="uq_attendance_records_student_date"),
        UniqueConstraint("id", "tenant_id", name="uq_attendance_records_id_tenant"),
        CheckConstraint(
            "status IN ('present', 'late', 'absent', 'excused', 'corrected')",
            name="ck_attendance_records_status",
        ),
    )


class AttendanceCorrection(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "attendance_corrections"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    attendance_record_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_entry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    new_entry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    previous_exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    new_exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["attendance_record_id", "tenant_id"],
            ["attendance_records.id", "attendance_records.tenant_id"],
            name="fk_attendance_corrections_record_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_attendance_corrections_id_tenant"),
    )


class AttendanceDailyRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "attendance_daily_runs"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "attendance_date", name="uq_attendance_daily_runs_tenant_date"),
        UniqueConstraint("id", "tenant_id", name="uq_attendance_daily_runs_id_tenant"),
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_attendance_daily_runs_status"),
    )


class AttendanceObservationProcessing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_observation_processing"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    rfid_observation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["rfid_observation_id", "tenant_id"],
            ["rfid_observations.id", "rfid_observations.tenant_id"],
            name="fk_attendance_obs_proc_observation_tenant",
        ),
        UniqueConstraint("rfid_observation_id", name="uq_attendance_observation_processing_obs"),
        UniqueConstraint("id", "tenant_id", name="uq_attendance_observation_processing_id_tenant"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'rejected', 'failed')",
            name="ck_attendance_observation_processing_status",
        ),
    )
