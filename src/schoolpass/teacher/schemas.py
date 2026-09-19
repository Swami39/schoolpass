"""Teacher-facing API models."""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field

from schoolpass.teacher.classes import TeacherClassSummary, TeacherStudentSummary
from schoolpass.teacher.notifications_inbox import TeacherNotificationRow
from schoolpass.teacher.profile import TeacherMeSummary
from schoolpass.teacher.results import AssessmentSummary, StudentMarkRow
from schoolpass.teacher.timetable import TimetablePeriodRow


class TeacherMeResponse(BaseModel):
    user_id: UUID
    email: str | None
    employee_code: str | None

    @classmethod
    def from_summary(cls, row: TeacherMeSummary) -> TeacherMeResponse:
        return cls(user_id=row.user_id, email=row.email, employee_code=row.employee_code)


class TeacherClassItem(BaseModel):
    section_id: UUID
    class_id: UUID
    class_name: str
    section_name: str
    subject_id: UUID | None
    subject_name: str | None
    academic_year_id: UUID
    student_count: int
    today_present_count: int
    today_absent_count: int

    @classmethod
    def from_summary(cls, row: TeacherClassSummary) -> TeacherClassItem:
        return cls(
            section_id=row.section_id,
            class_id=row.class_id,
            class_name=row.class_name,
            section_name=row.section_name,
            subject_id=row.subject_id,
            subject_name=row.subject_name,
            academic_year_id=row.academic_year_id,
            student_count=row.student_count,
            today_present_count=row.today_present_count,
            today_absent_count=row.today_absent_count,
        )


class TeacherClassListResponse(BaseModel):
    items: list[TeacherClassItem]


class TeacherStudentItem(BaseModel):
    id: UUID
    first_name: str
    middle_name: str | None
    last_name: str
    admission_no: str
    status: str

    @classmethod
    def from_summary(cls, row: TeacherStudentSummary) -> TeacherStudentItem:
        return cls(
            id=row.student_id,
            first_name=row.first_name,
            middle_name=row.middle_name,
            last_name=row.last_name,
            admission_no=row.admission_no,
            status=row.status,
        )


class TeacherStudentListResponse(BaseModel):
    items: list[TeacherStudentItem]


class TeacherAttendanceItem(BaseModel):
    id: UUID
    student_id: UUID
    attendance_date: date
    status: str
    entry_at: datetime | None
    exit_at: datetime | None
    source: str


class TeacherAttendanceListResponse(BaseModel):
    items: list[TeacherAttendanceItem]


class TeacherAttendanceMarkRequest(BaseModel):
    student_id: UUID
    status: str
    entry_at: datetime | None = None
    exit_at: datetime | None = None
    reason: str | None = None


class TeacherNfcSyncRequest(BaseModel):
    client_event_id: UUID
    section_id: UUID
    card_uid: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    device_sequence: int | None = None


class TeacherNfcSyncResponse(BaseModel):
    result: str
    client_event_id: UUID
    server_event_id: UUID
    attendance_record_id: UUID | None
    occurred_at: datetime
    received_at: datetime
    rejection_code: str | None


class TimetablePeriodItem(BaseModel):
    id: UUID
    section_id: UUID
    class_name: str
    section_name: str
    day_of_week: int
    period_number: int
    starts_at: time
    ends_at: time
    subject_id: UUID
    subject_name: str

    @classmethod
    def from_row(cls, row: TimetablePeriodRow) -> TimetablePeriodItem:
        return cls(
            id=row.id,
            section_id=row.section_id,
            class_name=row.class_name,
            section_name=row.section_name,
            day_of_week=row.day_of_week,
            period_number=row.period_number,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            subject_id=row.subject_id,
            subject_name=row.subject_name,
        )


class TimetableListResponse(BaseModel):
    items: list[TimetablePeriodItem]


class TimetablePeriodUpdate(BaseModel):
    starts_at: time | None = None
    ends_at: time | None = None
    subject_id: UUID | None = None
    teacher_user_id: UUID | None = None


class AssessmentItem(BaseModel):
    id: UUID
    section_id: UUID
    subject_id: UUID
    subject_name: str
    code: str
    name: str
    max_marks: int
    scheduled_on: date | None

    @classmethod
    def from_summary(cls, row: AssessmentSummary) -> AssessmentItem:
        return cls(
            id=row.id,
            section_id=row.section_id,
            subject_id=row.subject_id,
            subject_name=row.subject_name,
            code=row.code,
            name=row.name,
            max_marks=row.max_marks,
            scheduled_on=row.scheduled_on,
        )


class AssessmentListResponse(BaseModel):
    items: list[AssessmentItem]


class StudentMarkItem(BaseModel):
    student_id: UUID
    marks: int | None
    mark_id: UUID | None
    version: int | None

    @classmethod
    def from_row(cls, row: StudentMarkRow) -> StudentMarkItem:
        return cls(
            student_id=row.student_id,
            marks=row.marks,
            mark_id=row.mark_id,
            version=row.version,
        )


class AssessmentMarksResponse(BaseModel):
    assessment_id: UUID
    max_marks: int
    items: list[StudentMarkItem]


class StudentMarkUpsertRequest(BaseModel):
    marks: int


class TeacherMessageRequest(BaseModel):
    section_id: UUID | None = None
    student_id: UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    urgent: bool = False
    idempotency_key: str = Field(min_length=8, max_length=256)
    image_file_id: UUID | None = None


class TeacherClientDeviceRegisterRequest(BaseModel):
    device_uuid: UUID


class TeacherClientDeviceResponse(BaseModel):
    client_device_id: UUID


class TeacherMessageResponse(BaseModel):
    message_id: UUID
    recipient_count: int
    created: bool


class TeacherNotificationItem(BaseModel):
    id: UUID
    notification_type: str
    title: str
    body: str
    read: bool
    created_at: datetime

    @classmethod
    def from_row(cls, row: TeacherNotificationRow) -> TeacherNotificationItem:
        return cls(
            id=row.id,
            notification_type=row.notification_type,
            title=row.title,
            body=row.body,
            read=row.read_at is not None,
            created_at=row.created_at,
        )


class TeacherNotificationListResponse(BaseModel):
    items: list[TeacherNotificationItem]
