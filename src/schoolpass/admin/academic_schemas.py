from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AcademicYearResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    starts_on: date
    ends_on: date
    status: str
    created_at: datetime
    updated_at: datetime


class AcademicYearListResponse(BaseModel):
    items: list[AcademicYearResponse]


class AcademicYearCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    starts_on: date
    ends_on: date
    status: str = Field(default="active", pattern="^(active|inactive)$")

    @model_validator(mode="after")
    def ends_after_start(self) -> AcademicYearCreateRequest:
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on must be on or after starts_on")
        return self


class AcademicYearUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    starts_on: date | None = None
    ends_on: date | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class SchoolClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class SchoolClassListResponse(BaseModel):
    items: list[SchoolClassResponse]


class SchoolClassCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    status: str = Field(default="active", pattern="^(active|inactive)$")


class SchoolClassUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class SectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    class_id: UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class SectionListResponse(BaseModel):
    items: list[SectionResponse]


class SectionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_id: UUID
    name: str = Field(min_length=1, max_length=32)
    status: str = Field(default="active", pattern="^(active|inactive)$")


class SectionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=32)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class SubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class SubjectListResponse(BaseModel):
    items: list[SubjectResponse]


class SubjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    status: str = Field(default="active", pattern="^(active|inactive)$")


class SubjectUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class TeacherAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_user_id: UUID
    academic_year_id: UUID
    section_id: UUID
    subject_id: UUID | None
    assignment_role: str
    status: str
    created_at: datetime
    updated_at: datetime


class TeacherAssignmentListResponse(BaseModel):
    items: list[TeacherAssignmentResponse]


class TeacherAssignmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    teacher_user_id: UUID
    academic_year_id: UUID
    section_id: UUID
    subject_id: UUID | None = None
    assignment_role: str = Field(pattern="^(class_teacher|subject_teacher)$")
    status: str = Field(default="active", pattern="^(active|inactive)$")


class TeacherAssignmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: UUID | None = None
    assignment_role: str | None = Field(default=None, pattern="^(class_teacher|subject_teacher)$")
    status: str | None = Field(default=None, pattern="^(active|inactive)$")
