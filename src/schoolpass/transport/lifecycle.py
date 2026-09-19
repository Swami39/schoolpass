from __future__ import annotations

BUS_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"inactive", "maintenance", "retired"}),
    "maintenance": frozenset({"active", "inactive", "retired"}),
    "inactive": frozenset({"active", "retired"}),
    "retired": frozenset(),
}

ROUTE_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"inactive", "retired"}),
    "inactive": frozenset({"active", "retired"}),
    "retired": frozenset(),
}

TRIP_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "scheduled": frozenset({"boarding", "cancelled"}),
    "boarding": frozenset({"in_progress", "cancelled"}),
    "in_progress": frozenset({"completed", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}

ACTIVE_TRIP_STATUSES = frozenset({"scheduled", "boarding", "in_progress"})

TERMINAL_ASSIGNMENT_STATUSES = frozenset({"cancelled", "expired"})

BUS_OPERATIONAL_STATUS = "active"
ROUTE_OPERATIONAL_STATUS = "active"
ATTENDANT_OPERATIONAL_STATUS = "active"

VALID_SHIFTS = frozenset({"pickup", "dropoff"})
VALID_ROUTE_DIRECTIONS = frozenset({"pickup", "dropoff"})


def assert_bus_status_transition(current: str, new: str) -> None:
    allowed = BUS_STATUS_TRANSITIONS.get(current, frozenset())
    if new not in allowed:
        raise ValueError(f"Invalid bus status transition: {current} -> {new}")


def assert_route_status_transition(current: str, new: str) -> None:
    allowed = ROUTE_STATUS_TRANSITIONS.get(current, frozenset())
    if new not in allowed:
        raise ValueError(f"Invalid route status transition: {current} -> {new}")


def assert_trip_status_transition(current: str, new: str) -> None:
    allowed = TRIP_STATUS_TRANSITIONS.get(current, frozenset())
    if new not in allowed:
        raise ValueError(f"Invalid trip status transition: {current} -> {new}")
