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


class Subject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subjects"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_subjects_id_tenant"),
        UniqueConstraint("tenant_id", "code", name="uq_subjects_tenant_code"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_subjects_status"),
    )


class TeacherSectionAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teacher_section_assignments"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    teacher_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    academic_year_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    section_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    subject_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    assignment_role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["academic_year_id", "tenant_id"],
            ["academic_years.id", "academic_years.tenant_id"],
            name="fk_teacher_assign_year_tenant",
        ),
        ForeignKeyConstraint(
            ["section_id", "tenant_id"],
            ["sections.id", "sections.tenant_id"],
            name="fk_teacher_assign_section_tenant",
        ),
        ForeignKeyConstraint(
            ["subject_id", "tenant_id"],
            ["subjects.id", "subjects.tenant_id"],
            name="fk_teacher_assign_subject_tenant",
        ),
        ForeignKeyConstraint(
            ["teacher_user_id", "tenant_id"],
            ["staff_profiles.user_id", "staff_profiles.tenant_id"],
            name="fk_teacher_assign_staff_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_teacher_section_assignments_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "teacher_user_id",
            "academic_year_id",
            "section_id",
            "subject_id",
            name="uq_teacher_section_assignments_teacher_section_subject",
        ),
        CheckConstraint(
            "assignment_role IN ('class_teacher', 'subject_teacher')",
            name="ck_teacher_section_assignments_role",
        ),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_teacher_section_assignments_status"),
    )


class TimetablePeriod(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "timetable_periods"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    academic_year_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    section_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[time] = mapped_column(Time, nullable=False)
    ends_at: Mapped[time] = mapped_column(Time, nullable=False)
    subject_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    teacher_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["academic_year_id", "tenant_id"],
            ["academic_years.id", "academic_years.tenant_id"],
            name="fk_timetable_year_tenant",
        ),
        ForeignKeyConstraint(
            ["section_id", "tenant_id"],
            ["sections.id", "sections.tenant_id"],
            name="fk_timetable_section_tenant",
        ),
        ForeignKeyConstraint(
            ["subject_id", "tenant_id"],
            ["subjects.id", "subjects.tenant_id"],
            name="fk_timetable_subject_tenant",
        ),
        ForeignKeyConstraint(
            ["teacher_user_id", "tenant_id"],
            ["staff_profiles.user_id", "staff_profiles.tenant_id"],
            name="fk_timetable_teacher_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_timetable_periods_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "academic_year_id",
            "section_id",
            "day_of_week",
            "period_number",
            name="uq_timetable_period_slot",
        ),
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_timetable_day_of_week"),
        CheckConstraint("period_number > 0", name="ck_timetable_period_number"),
    )


class Assessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessments"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    academic_year_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    section_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["academic_year_id", "tenant_id"],
            ["academic_years.id", "academic_years.tenant_id"],
            name="fk_assessments_year_tenant",
        ),
        ForeignKeyConstraint(
            ["section_id", "tenant_id"],
            ["sections.id", "sections.tenant_id"],
            name="fk_assessments_section_tenant",
        ),
        ForeignKeyConstraint(
            ["subject_id", "tenant_id"],
            ["subjects.id", "subjects.tenant_id"],
            name="fk_assessments_subject_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_assessments_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "academic_year_id",
            "section_id",
            "subject_id",
            "code",
            name="uq_assessments_section_subject_code",
        ),
        CheckConstraint("max_marks > 0", name="ck_assessments_max_marks"),
        CheckConstraint("status IN ('active', 'archived')", name="ck_assessments_status"),
    )


class StudentAssessmentMark(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_assessment_marks"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    assessment_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    student_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    marks: Mapped[int] = mapped_column(Integer, nullable=False)
    entered_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["assessment_id", "tenant_id"],
            ["assessments.id", "assessments.tenant_id"],
            name="fk_student_marks_assessment_tenant",
        ),
        ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_student_marks_student_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_student_assessment_marks_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "assessment_id",
            "student_id",
            name="uq_student_assessment_marks_student_assessment",
        ),
        CheckConstraint("marks >= 0", name="ck_student_assessment_marks_nonneg"),
    )


class TeacherClassNfcEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "teacher_class_nfc_events"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    client_device_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    client_event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    teacher_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    section_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    card_hf_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    student_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    attendance_record_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processing_state: Mapped[str] = mapped_column(String(64), nullable=False)
    rejection_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["section_id", "tenant_id"],
            ["sections.id", "sections.tenant_id"],
            name="fk_teacher_nfc_section_tenant",
        ),
        UniqueConstraint("client_device_id", "client_event_id", name="uq_teacher_nfc_device_event"),
        UniqueConstraint("id", "tenant_id", name="uq_teacher_class_nfc_events_id_tenant"),
    )


class TeacherMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teacher_messages"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    teacher_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    section_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    student_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    urgent: Mapped[bool] = mapped_column(default=False, nullable=False)
    image_file_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["image_file_id", "tenant_id"],
            ["files.id", "files.tenant_id"],
            name="fk_teacher_messages_file_tenant",
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_teacher_messages_idempotency"),
        UniqueConstraint("id", "tenant_id", name="uq_teacher_messages_id_tenant"),
    )
