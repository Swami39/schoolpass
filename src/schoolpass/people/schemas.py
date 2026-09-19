from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    admission_no: str = Field(min_length=1, max_length=64)
    first_name: str = Field(min_length=1, max_length=128)
    middle_name: str | None = Field(default=None, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    date_of_birth: date | None = None
    photo_file_id: UUID | None = None


class StudentUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=128)
    middle_name: str | None = Field(default=None, max_length=128)
    last_name: str | None = Field(default=None, min_length=1, max_length=128)
    date_of_birth: date | None = None
    photo_file_id: UUID | None = None


class StudentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    historical_subject_id: UUID
    admission_no: str
    first_name: str
    middle_name: str | None
    last_name: str
    date_of_birth: date | None
    photo_file_id: UUID | None
    status: str
    pii_state: str
    created_at: datetime
    updated_at: datetime


class StudentListResponse(BaseModel):
    items: list[StudentResponse]
    next_cursor: str | None = None


class GuardianCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    phone_e164: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)


class GuardianUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=128)
    last_name: str | None = Field(default=None, min_length=1, max_length=128)
    phone_e164: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    status: str | None = None


class GuardianResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    first_name: str
    last_name: str
    phone_e164: str | None
    email: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class GuardianListResponse(BaseModel):
    items: list[GuardianResponse]
    next_cursor: str | None = None


class StudentGuardianCreate(BaseModel):
    guardian_id: UUID
    relationship_type: str = Field(min_length=1, max_length=32)
    is_primary_contact: bool = False
    can_receive_notifications: bool = True
    can_pay_fees: bool = False


class StudentGuardianUpdate(BaseModel):
    relationship_type: str | None = Field(default=None, max_length=32)
    is_primary_contact: bool | None = None
    can_receive_notifications: bool | None = None
    can_pay_fees: bool | None = None
    status: str | None = None


class StudentGuardianResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    student_id: UUID
    guardian_id: UUID
    relationship_type: str
    is_primary_contact: bool
    can_receive_notifications: bool
    can_pay_fees: bool
    status: str
    created_at: datetime
    updated_at: datetime


class StudentGuardianListResponse(BaseModel):
    items: list[StudentGuardianResponse]
    next_cursor: str | None = None


class AcademicYearCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    starts_on: date
    ends_on: date


class SchoolClassCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)


class SectionCreate(BaseModel):
    class_id: UUID
    name: str = Field(min_length=1, max_length=32)


class EnrollmentCreate(BaseModel):
    student_id: UUID
    academic_year_id: UUID
    class_id: UUID
    section_id: UUID
    starts_on: date


class EnrollmentClose(BaseModel):
    ends_on: date
    status: str = Field(default="completed", pattern="^(completed|withdrawn)$")


class EnrollmentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    student_id: UUID
    academic_year_id: UUID
    class_id: UUID
    section_id: UUID
    status: str
    starts_on: date
    ends_on: date | None
    created_at: datetime
    updated_at: datetime


class EnrollmentListResponse(BaseModel):
    items: list[EnrollmentResponse]
    next_cursor: str | None = None
