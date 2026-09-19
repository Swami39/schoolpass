from __future__ import annotations

CARD_PROFILES = frozenset({"uid_only", "ntag_sig", "desfire"})

CARD_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "inventory": frozenset({"active", "blocked"}),
    "active": frozenset({"blocked", "retired"}),
    "blocked": frozenset({"active", "retired"}),
    "retired": frozenset(),
}

TERMINAL_ASSIGNMENT_STATUSES = frozenset({"lost", "blocked", "expired", "replaced", "revoked"})


def assert_card_status_transition(current: str, new: str) -> None:
    allowed = CARD_STATUS_TRANSITIONS.get(current, frozenset())
    if new not in allowed:
        raise ValueError(f"Invalid card status transition: {current} -> {new}")
