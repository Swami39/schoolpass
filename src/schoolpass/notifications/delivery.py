from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.db.mixins import utcnow
from schoolpass.notifications.constants import (
    DELIVERY_STATUS_FAILED,
    DELIVERY_STATUS_PENDING,
    DELIVERY_STATUS_SENT,
    DELIVERY_STATUS_SKIPPED_NO_DEVICE,
    DELIVERY_STATUS_SKIPPED_PREFERENCE,
)
from schoolpass.notifications.devices import list_active_devices_for_user
from schoolpass.notifications.fcm import FcmHttpV1Provider, FcmSendResult
from schoolpass.notifications.models import Notification, NotificationDelivery, NotificationDevice
from schoolpass.notifications.preferences import is_push_enabled


class NotificationDeliveryService:
    def __init__(self, *, fcm: FcmHttpV1Provider, max_attempts: int = 3) -> None:
        self._fcm = fcm
        self._max_attempts = max_attempts

    async def deliver_notification(self, session: AsyncSession, *, notification: Notification) -> str:
        if notification.delivery_status == DELIVERY_STATUS_SENT:
            return "duplicate_ok"

        push_ok = await is_push_enabled(
            session,
            tenant_id=notification.tenant_id,
            user_id=notification.recipient_user_id,
            notification_type=notification.notification_type,
        )
        if not push_ok:
            notification.delivery_status = DELIVERY_STATUS_SKIPPED_PREFERENCE
            notification.updated_at = utcnow()
            await session.flush()
            return DELIVERY_STATUS_SKIPPED_PREFERENCE

        devices = await list_active_devices_for_user(
            session,
            tenant_id=notification.tenant_id,
            user_id=notification.recipient_user_id,
        )
        if not devices:
            notification.delivery_status = DELIVERY_STATUS_SKIPPED_NO_DEVICE
            notification.updated_at = utcnow()
            await session.flush()
            return DELIVERY_STATUS_SKIPPED_NO_DEVICE

        data = {
            "notification_id": str(notification.id),
            "notification_type": notification.notification_type,
        }
        any_sent = False
        any_failed = False
        for device in devices:
            attempt = (
                await session.execute(
                    select(func.count())
                    .select_from(NotificationDelivery)
                    .where(
                        NotificationDelivery.tenant_id == notification.tenant_id,
                        NotificationDelivery.notification_id == notification.id,
                        NotificationDelivery.device_id == device.id,
                    )
                )
            ).scalar_one()
            attempt_no = int(attempt) + 1
            if attempt_no > self._max_attempts:
                any_failed = True
                continue
            result = await self._fcm.send_push(
                token=device.fcm_token,
                title=notification.title,
                body=notification.body,
                data=data,
            )
            await self._record_attempt(
                session,
                notification=notification,
                device_id=device.id,
                attempt=attempt_no,
                result=result,
            )
            await self._apply_device_result(session, device, result)
            if result.ok:
                any_sent = True
            else:
                any_failed = True

        if any_sent:
            notification.delivery_status = DELIVERY_STATUS_SENT
        elif any_failed:
            notification.delivery_status = DELIVERY_STATUS_FAILED
        else:
            notification.delivery_status = DELIVERY_STATUS_PENDING
        notification.updated_at = utcnow()
        await session.flush()
        return notification.delivery_status

    async def _record_attempt(
        self,
        session: AsyncSession,
        *,
        notification: Notification,
        device_id: UUID,
        attempt: int,
        result: FcmSendResult,
    ) -> None:
        status = "sent" if result.ok else "failed"
        session.add(
            NotificationDelivery(
                tenant_id=notification.tenant_id,
                notification_id=notification.id,
                device_id=device_id,
                provider="fcm",
                attempt=attempt,
                status=status,
                provider_message_id=result.message_id,
                failure_code=result.error_code,
            )
        )
        await session.flush()

    async def _apply_device_result(
        self,
        session: AsyncSession,
        device: NotificationDevice,
        result: FcmSendResult,
    ) -> None:
        now = datetime.now(UTC)
        if result.ok:
            device.last_success_at = now
            device.last_failure_code = None
        else:
            device.last_failure_at = now
            device.last_failure_code = result.error_code
            if result.invalid_token:
                device.status = "revoked"
        device.updated_at = now
        await session.flush()
