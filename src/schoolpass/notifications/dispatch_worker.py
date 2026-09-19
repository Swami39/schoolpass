from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.db.session import apply_tenant_context
from schoolpass.notifications.constants import (
    DELIVERY_STATUS_SENT,
    DELIVERY_STATUS_SKIPPED_NO_DEVICE,
    DELIVERY_STATUS_SKIPPED_PREFERENCE,
    NOTIFICATION_SCHEMA_VERSION,
    OUTBOX_DISPATCH_SCHEMA_VERSION,
)
from schoolpass.notifications.delivery import NotificationDeliveryService
from schoolpass.notifications.models import Notification
from schoolpass.observability.logging import get_logger
from schoolpass.tenancy.context import TenantContext

log = get_logger("schoolpass.notifications.dispatch")


@dataclass(frozen=True)
class DispatchOutcome:
    status: str
    notification_id: UUID | None = None


def _parse_bus_message(raw: dict[str, Any]) -> tuple[UUID, UUID | None, int, dict[str, Any]] | None:
    try:
        event_id = UUID(str(raw["id"]))
        tenant_raw = raw.get("tenant_id")
        tenant_id = UUID(str(tenant_raw)) if tenant_raw else None
        schema_version = int(raw.get("schema_version", 0))
        payload = raw.get("payload") or {}
        if not isinstance(payload, dict):
            return None
        return event_id, tenant_id, schema_version, payload
    except (TypeError, ValueError, KeyError):
        return None


async def process_notification_dispatch_message(
    session: AsyncSession,
    *,
    message: dict[str, Any],
    delivery: NotificationDeliveryService,
) -> DispatchOutcome:
    parsed = _parse_bus_message(message)
    if parsed is None:
        log.warning("notification_dispatch_malformed")
        return DispatchOutcome(status="rejected_malformed")
    _event_id, tenant_id, schema_version, payload = parsed
    if schema_version != OUTBOX_DISPATCH_SCHEMA_VERSION:
        log.warning("notification_dispatch_bad_schema", schema_version=schema_version)
        return DispatchOutcome(status="rejected_schema")
    if tenant_id is None:
        return DispatchOutcome(status="rejected_tenant")
    notification_id_raw = payload.get("notification_id")
    if notification_id_raw is None:
        return DispatchOutcome(status="rejected_payload")
    try:
        notification_id = UUID(str(notification_id_raw))
    except ValueError:
        return DispatchOutcome(status="rejected_payload")

    await apply_tenant_context(
        session,
        TenantContext(actor_type="worker", tenant_id=tenant_id, user_id=None),
    )
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.tenant_id != tenant_id:
        log.warning("notification_dispatch_tenant_mismatch", notification_id=str(notification_id))
        return DispatchOutcome(status="rejected_tenant")
    if notification.schema_version != NOTIFICATION_SCHEMA_VERSION:
        return DispatchOutcome(status="rejected_schema")

    if notification.delivery_status in (
        DELIVERY_STATUS_SENT,
        DELIVERY_STATUS_SKIPPED_PREFERENCE,
        DELIVERY_STATUS_SKIPPED_NO_DEVICE,
    ):
        return DispatchOutcome(status="duplicate_ok", notification_id=notification_id)

    outcome = await delivery.deliver_notification(session, notification=notification)
    log.info(
        "notification_dispatch_processed",
        notification_id=str(notification.id),
        tenant_id=str(tenant_id),
        status=outcome,
        correlation_id=notification.correlation_id,
    )
    return DispatchOutcome(status=outcome, notification_id=notification_id)
