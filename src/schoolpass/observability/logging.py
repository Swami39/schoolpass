from __future__ import annotations

import logging
from collections.abc import MutableMapping
from typing import Any

import structlog

_REDACT_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "otp",
    "secret",
    "jwt",
    "private_key",
    "webhook",
}


def _redact(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    for key in list(event_dict.keys()):
        lowered = key.lower()
        if any(part in lowered for part in _REDACT_KEYS):
            event_dict[key] = "[redacted]"
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_request_context(
    *,
    request_id: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
    actor_type: str | None = None,
) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        actor_type=actor_type,
    )


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)
