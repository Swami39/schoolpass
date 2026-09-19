"""Parent-facing API response models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from schoolpass.attendance.models import AttendanceRecord
from schoolpass.parent.bus_location import ParentBusLocationResult, ParentBusLocationStatus
from schoolpass.parent.children import ParentChildSummary
from schoolpass.parent.notification_preferences_read import ParentNotificationPreferenceItem
from schoolpass.parent.notifications_inbox import ParentNotificationRow


class ParentBusLocationResponse(BaseModel):
    student_id: UUID
    status: str
    bus_id: UUID | None = None
    trip_id: UUID | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    occurred_at: str | None = None
    received_at: str | None = None
    accuracy_meters: Decimal | None = None

    @classmethod
    def from_result(cls, result: ParentBusLocationResult) -> ParentBusLocationResponse:
        return cls(
            student_id=result.student_id,
            status=result.status.value,
            bus_id=result.bus_id,
            trip_id=result.trip_id,
            latitude=result.latitude if result.status == ParentBusLocationStatus.AVAILABLE else None,
            longitude=result.longitude if result.status == ParentBusLocationStatus.AVAILABLE else None,
            occurred_at=result.occurred_at.isoformat() if result.occurred_at else None,
            received_at=result.received_at.isoformat() if result.received_at else None,
            accuracy_meters=result.accuracy_meters if result.status == ParentBusLocationStatus.AVAILABLE else None,
        )


class ParentChildItem(BaseModel):
    id: UUID
    first_name: str
    middle_name: str | None
    last_name: str
    admission_no: str
    status: str

    @classmethod
    def from_summary(cls, row: ParentChildSummary) -> ParentChildItem:
        return cls(
            id=row.student_id,
            first_name=row.first_name,
            middle_name=row.middle_name,
            last_name=row.last_name,
            admission_no=row.admission_no,
            status=row.status,
        )


class ParentChildrenListResponse(BaseModel):
    items: list[ParentChildItem]


class ParentAttendanceRecordItem(BaseModel):
    id: UUID
    student_id: UUID
    attendance_date: date
    status: str
    entry_at: datetime | None
    exit_at: datetime | None

    @classmethod
    def from_record(cls, row: AttendanceRecord) -> ParentAttendanceRecordItem:
        return cls(
            id=row.id,
            student_id=row.student_id,
            attendance_date=row.attendance_date,
            status=row.status,
            entry_at=row.entry_at,
            exit_at=row.exit_at,
        )


class ParentAttendanceListResponse(BaseModel):
    items: list[ParentAttendanceRecordItem]


class ParentNotificationItem(BaseModel):
    id: UUID
    notification_type: str
    title: str
    body: str
    read: bool
    created_at: datetime
    student_id: UUID | None = None

    @classmethod
    def from_row(cls, row: ParentNotificationRow) -> ParentNotificationItem:
        return cls(
            id=row.id,
            notification_type=row.notification_type,
            title=row.title,
            body=row.body,
            read=row.read_at is not None,
            created_at=row.created_at,
            student_id=row.student_id,
        )


class ParentNotificationListResponse(BaseModel):
    items: list[ParentNotificationItem]


class ParentNotificationPreferenceResponseItem(BaseModel):
    notification_type: str
    push_enabled: bool

    @classmethod
    def from_item(cls, row: ParentNotificationPreferenceItem) -> ParentNotificationPreferenceResponseItem:
        return cls(notification_type=row.notification_type, push_enabled=row.push_enabled)


class ParentNotificationPreferencesResponse(BaseModel):
    items: list[ParentNotificationPreferenceResponseItem]


class ParentNotificationPreferenceUpdateItem(BaseModel):
    notification_type: str = Field(min_length=2, max_length=64)
    push_enabled: bool


class ParentNotificationPreferencesUpdateRequest(BaseModel):
    items: list[ParentNotificationPreferenceUpdateItem]
