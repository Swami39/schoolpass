from __future__ import annotations

from datetime import UTC, date, datetime, time
from uuid import uuid4

from schoolpass.attendance.models import AttendancePolicy
from schoolpass.attendance.rules import (
    dedupe_key,
    entry_status_for_time,
    policy_covers_date,
    resolve_signal_direction,
    school_local_date,
)


def test_resolve_direction_entry_reader() -> None:
    assert resolve_signal_direction(reader_direction_mode="entry", event_direction="exit") == "entry"


def test_resolve_direction_both_requires_event() -> None:
    assert resolve_signal_direction(reader_direction_mode="both", event_direction="entry") == "entry"
    assert resolve_signal_direction(reader_direction_mode="both", event_direction=None) is None


def test_school_local_date_uses_timezone() -> None:
    observed = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
    assert school_local_date(observed, "Asia/Kolkata") == date(2026, 9, 19)


def test_dedupe_key_changes_with_bucket() -> None:
    t1 = datetime(2026, 9, 19, 2, 32, 1, tzinfo=UTC)
    t2 = datetime(2026, 9, 19, 2, 32, 25, tzinfo=UTC)
    k1 = dedupe_key(
        student_id="s1",
        attendance_date=date(2026, 9, 19),
        direction="entry",
        observed_at=t1,
        dedupe_seconds=30,
    )
    k2 = dedupe_key(
        student_id="s1",
        attendance_date=date(2026, 9, 19),
        direction="entry",
        observed_at=t2,
        dedupe_seconds=30,
    )
    assert k1 == k2


def test_entry_status_present_vs_late() -> None:
    policy = AttendancePolicy(
        tenant_id=uuid4(),
        name="p",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        entry_start_time=time(7, 0),
        present_until=time(8, 15),
        late_until=time(9, 0),
        entry_dedupe_seconds=30,
        exit_dedupe_seconds=30,
    )
    assert entry_status_for_time(policy, time(8, 10)) == "present"
    assert entry_status_for_time(policy, time(8, 37)) == "late"


def test_policy_covers_date_range() -> None:
    policy = AttendancePolicy(
        tenant_id=uuid4(),
        name="p",
        effective_from=date(2026, 9, 1),
        effective_to=date(2026, 9, 30),
        entry_start_time=None,
        present_until=None,
        late_until=None,
        entry_dedupe_seconds=30,
        exit_dedupe_seconds=30,
    )
    assert policy_covers_date(policy, date(2026, 9, 15))
    assert not policy_covers_date(policy, date(2026, 10, 1))
