from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from schoolpass.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from schoolpass.db.session import Base


class FileMetadata(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "files"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    blob_key: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification: Mapped[str] = mapped_column(String(64), default="SENSITIVE_CHILD_DATA", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_files_id_tenant"),
        UniqueConstraint("tenant_id", "blob_key", name="uq_files_tenant_blob_key"),
    )


class AcademicYear(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "academic_years"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_academic_years_id_tenant"),
        UniqueConstraint("tenant_id", "code", name="uq_academic_years_tenant_code"),
        CheckConstraint("ends_on >= starts_on", name="ck_academic_years_dates"),
    )


class SchoolClass(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "classes"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_classes_id_tenant"),
        UniqueConstraint("tenant_id", "code", name="uq_classes_tenant_code"),
    )


class Section(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sections"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    class_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["class_id", "tenant_id"],
            ["classes.id", "classes.tenant_id"],
            name="fk_sections_class_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_sections_id_tenant"),
        UniqueConstraint("tenant_id", "class_id", "name", name="uq_sections_tenant_class_name"),
    )


class Student(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "students"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    historical_subject_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    admission_no: Mapped[str] = mapped_column(String(64), nullable=False)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    photo_file_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    pii_state: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["photo_file_id", "tenant_id"],
            ["files.id", "files.tenant_id"],
            name="fk_students_photo_file_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_students_id_tenant"),
        UniqueConstraint("tenant_id", "admission_no", name="uq_students_tenant_admission_no"),
        CheckConstraint("status IN ('active', 'withdrawn')", name="ck_students_status"),
        CheckConstraint("pii_state IN ('active', 'hidden', 'anonymized')", name="ck_students_pii_state"),
    )


class Guardian(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "guardians"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    phone_e164: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_guardians_id_tenant"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_guardians_status"),
    )


class StudentGuardian(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_guardians"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    student_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    guardian_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_primary_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_receive_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_pay_fees: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_student_guardians_student_tenant",
        ),
        ForeignKeyConstraint(
            ["guardian_id", "tenant_id"],
            ["guardians.id", "guardians.tenant_id"],
            name="fk_student_guardians_guardian_tenant",
        ),
        UniqueConstraint("tenant_id", "student_id", "guardian_id", name="uq_student_guardians_pair"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_student_guardians_status"),
    )


class Enrollment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enrollments"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    student_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    academic_year_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    class_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    section_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_enrollments_student_tenant",
        ),
        ForeignKeyConstraint(
            ["academic_year_id", "tenant_id"],
            ["academic_years.id", "academic_years.tenant_id"],
            name="fk_enrollments_year_tenant",
        ),
        ForeignKeyConstraint(
            ["class_id", "tenant_id"],
            ["classes.id", "classes.tenant_id"],
            name="fk_enrollments_class_tenant",
        ),
        ForeignKeyConstraint(
            ["section_id", "tenant_id"],
            ["sections.id", "sections.tenant_id"],
            name="fk_enrollments_section_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_enrollments_id_tenant"),
        CheckConstraint("status IN ('active', 'completed', 'withdrawn')", name="ck_enrollments_status"),
        CheckConstraint("ends_on IS NULL OR ends_on >= starts_on", name="ck_enrollments_dates"),
    )
