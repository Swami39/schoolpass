from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from schoolpass.attendance.models import AttendancePolicy

DIRECTION_ENTRY = "entry"
DIRECTION_EXIT = "exit"

READER_MODES = frozenset({"entry", "exit", "both"})


def resolve_signal_direction(
    *,
    reader_direction_mode: str | None,
    event_direction: str | None,
) -> str | None:
    mode = (reader_direction_mode or "entry").lower()
    if mode not in READER_MODES:
        mode = "entry"
    event_dir = (event_direction or "").lower().strip()
    if mode == "entry":
        return DIRECTION_ENTRY
    if mode == "exit":
        return DIRECTION_EXIT
    if event_dir in {DIRECTION_ENTRY, DIRECTION_EXIT}:
        return event_dir
    return None


def school_local_date(observed_at: datetime, timezone_name: str) -> date:
    tz = ZoneInfo(timezone_name)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=ZoneInfo("UTC"))
    return observed_at.astimezone(tz).date()


def school_local_time(observed_at: datetime, timezone_name: str) -> time:
    tz = ZoneInfo(timezone_name)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=ZoneInfo("UTC"))
    return observed_at.astimezone(tz).timetz().replace(tzinfo=None)


def dedupe_key(
    *,
    student_id: str,
    attendance_date: date,
    direction: str,
    observed_at: datetime,
    dedupe_seconds: int,
) -> str:
    bucket = int(observed_at.timestamp()) // max(dedupe_seconds, 1)
    return f"{student_id}:{attendance_date.isoformat()}:{direction}:{bucket}"


def entry_status_for_time(policy: AttendancePolicy, local_time: time) -> str:
    if policy.present_until and local_time <= policy.present_until:
        if policy.entry_start_time and local_time < policy.entry_start_time:
            return "present"
        return "present"
    if policy.late_until and local_time <= policy.late_until:
        return "late"
    return "late"


def is_weekend(attendance_date: date) -> bool:
    return attendance_date.weekday() >= 5


def policy_covers_date(policy: AttendancePolicy, on_date: date) -> bool:
    if on_date < policy.effective_from:
        return False
    if policy.effective_to is not None and on_date > policy.effective_to:
        return False
    return True
