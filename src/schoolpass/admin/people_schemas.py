from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from schoolpass.identity.models import StaffProfile, User
from schoolpass.people import schemas as people_schemas


class AdminStudentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    admission_no: str = Field(min_length=1, max_length=64)
    first_name: str = Field(min_length=1, max_length=128)
    middle_name: str | None = Field(default=None, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    date_of_birth: date | None = None
    photo_file_id: UUID | None = None


class AdminStudentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=128)
    middle_name: str | None = Field(default=None, max_length=128)
    last_name: str | None = Field(default=None, min_length=1, max_length=128)
    date_of_birth: date | None = None
    photo_file_id: UUID | None = None


class AdminGuardianCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    phone_e164: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    create_parent_login: bool = True


class AdminGuardianUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=128)
    last_name: str | None = Field(default=None, min_length=1, max_length=128)
    phone_e164: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class AdminEnrollmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    academic_year_id: UUID
    class_id: UUID
    section_id: UUID
    starts_on: date


class AdminEnrollmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_id: UUID | None = None
    section_id: UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|completed|withdrawn)$")


class AdminEnrollmentClose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ends_on: date
    status: str = Field(default="completed", pattern="^(completed|withdrawn)$")


class AdminStudentGuardianCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guardian_id: UUID
    relationship_type: str = Field(min_length=1, max_length=32)
    is_primary_contact: bool = False
    can_receive_notifications: bool = True
    can_pay_fees: bool = False


class AdminStudentGuardianUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_type: str | None = Field(default=None, max_length=32)
    is_primary_contact: bool | None = None
    can_receive_notifications: bool | None = None
    can_pay_fees: bool | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class AdminStaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    staff_type: str = Field(min_length=1, max_length=32)
    employee_code: str | None = Field(default=None, max_length=64)


class AdminStaffUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_type: str | None = Field(default=None, max_length=32)
    employee_code: str | None = Field(default=None, max_length=64)


class AdminStaffResponse(BaseModel):
    id: UUID
    user_id: UUID
    staff_type: str
    employee_code: str | None
    email: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, staff: StaffProfile, user: User | None) -> AdminStaffResponse:
        email = user.email if user is not None else None
        return cls.model_validate(
            {
                "id": staff.id,
                "user_id": staff.user_id,
                "staff_type": staff.staff_type,
                "employee_code": staff.employee_code,
                "email": email,
                "created_at": staff.created_at,
                "updated_at": staff.updated_at,
            }
        )


class AdminStaffListResponse(BaseModel):
    items: list[AdminStaffResponse]
    next_cursor: str | None = None


# Re-export stable people responses for admin routes.
StudentResponse = people_schemas.StudentResponse
StudentListResponse = people_schemas.StudentListResponse
GuardianResponse = people_schemas.GuardianResponse
GuardianListResponse = people_schemas.GuardianListResponse
StudentGuardianResponse = people_schemas.StudentGuardianResponse
StudentGuardianListResponse = people_schemas.StudentGuardianListResponse
EnrollmentResponse = people_schemas.EnrollmentResponse
EnrollmentListResponse = people_schemas.EnrollmentListResponse
