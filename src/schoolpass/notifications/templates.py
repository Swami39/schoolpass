from __future__ import annotations

from dataclasses import dataclass

from schoolpass.notifications.constants import (
    NOTIFICATION_TYPE_BUS_BOARDING,
    NOTIFICATION_TYPE_BUS_DROPOFF,
    NOTIFICATION_TYPE_SCHOOL_ENTRY,
    NOTIFICATION_TYPE_SCHOOL_EXIT,
)

ALLOWED_PLACEHOLDERS = frozenset({"student_display_name", "school_display_name", "bus_display_name"})


@dataclass(frozen=True)
class RenderedNotification:
    title: str
    body: str


_STATIC: dict[str, tuple[str, str]] = {
    NOTIFICATION_TYPE_SCHOOL_ENTRY: ("School entry", "Your child has entered school."),
    NOTIFICATION_TYPE_SCHOOL_EXIT: ("School exit", "Your child has left school."),
    NOTIFICATION_TYPE_BUS_BOARDING: ("Bus boarding", "Your child has boarded the school bus."),
    NOTIFICATION_TYPE_BUS_DROPOFF: ("Bus dropoff", "Your child has been dropped off."),
}


def render_notification(
    notification_type: str,
    *,
    student_display_name: str | None = None,
    school_display_name: str | None = None,
    bus_display_name: str | None = None,
) -> RenderedNotification:
    base_title, base_body = _STATIC.get(notification_type, ("Notification", "You have a new notification."))
    title = base_title
    body = base_body
    if student_display_name:
        body = f"{body} ({student_display_name})"
    if school_display_name and "{school_display_name}" in body:
        body = body.replace("{school_display_name}", school_display_name)
    if bus_display_name and notification_type in (NOTIFICATION_TYPE_BUS_BOARDING, NOTIFICATION_TYPE_BUS_DROPOFF):
        body = f"{body} ({bus_display_name})"
    return RenderedNotification(title=title[:255], body=body)


def validate_template_placeholders(names: set[str]) -> None:
    unknown = names - ALLOWED_PLACEHOLDERS
    if unknown:
        raise ValueError(f"unsupported placeholders: {sorted(unknown)}")
