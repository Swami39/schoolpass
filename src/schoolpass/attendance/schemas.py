from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AttendancePolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    effective_from: date
    effective_to: date | None = None
    entry_start_time: time | None = None
    present_until: time | None = None
    late_until: time | None = None
    entry_dedupe_seconds: int = Field(default=30, ge=1, le=3600)
    exit_dedupe_seconds: int = Field(default=30, ge=1, le=3600)


class AttendancePolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    effective_to: date | None = None
    entry_start_time: time | None = None
    present_until: time | None = None
    late_until: time | None = None
    entry_dedupe_seconds: int | None = Field(default=None, ge=1, le=3600)
    exit_dedupe_seconds: int | None = Field(default=None, ge=1, le=3600)


class AttendancePolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    effective_from: date
    effective_to: date | None
    entry_start_time: time | None
    present_until: time | None
    late_until: time | None
    entry_dedupe_seconds: int
    exit_dedupe_seconds: int
    created_at: datetime
    updated_at: datetime


class AttendancePolicyListResponse(BaseModel):
    items: list[AttendancePolicyResponse]


class AttendanceRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    student_id: UUID
    academic_year_id: UUID | None
    attendance_date: date
    status: str
    entry_at: datetime | None
    exit_at: datetime | None
    source: str
    version: int
    created_at: datetime
    updated_at: datetime


class AttendanceListResponse(BaseModel):
    items: list[AttendanceRecordResponse]
    next_cursor: str | None = None


class AttendanceSummaryResponse(BaseModel):
    date: date
    present: int
    late: int
    absent: int
    excused: int
    corrected: int
    unresolved: int


class AttendanceCorrectionCreate(BaseModel):
    status: str
    entry_at: datetime | None = None
    exit_at: datetime | None = None
    reason: str = Field(min_length=3)


class AttendanceFinalizeRequest(BaseModel):
    date: date


class AttendanceFinalizeResponse(BaseModel):
    attendance_date: date
    status: str
    run_id: UUID
