from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.notifications.models import NotificationDevice


@dataclass(frozen=True)
class RegisteredDevice:
    device: NotificationDevice
    created: bool


async def register_fcm_device(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    platform: str,
    fcm_token: str,
    app_label: str | None = None,
) -> RegisteredDevice:
    now = datetime.now(UTC)
    existing = (
        await session.execute(
            select(NotificationDevice).where(
                NotificationDevice.tenant_id == tenant_id,
                NotificationDevice.fcm_token == fcm_token,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.user_id != user_id:
            raise PermissionError("token registered to another user")
        existing.status = "active"
        existing.platform = platform
        if app_label is not None:
            existing.app_label = app_label
        existing.last_seen_at = now
        existing.updated_at = now
        await session.flush()
        return RegisteredDevice(device=existing, created=False)

    device = NotificationDevice(
        tenant_id=tenant_id,
        user_id=user_id,
        platform=platform,
        fcm_token=fcm_token,
        status="active",
        app_label=app_label,
        last_seen_at=now,
    )
    try:
        async with session.begin_nested():
            session.add(device)
            await session.flush()
    except IntegrityError:
        # Lost a race with a concurrent registration: re-read and treat as existing.
        row = (
            await session.execute(
                select(NotificationDevice).where(
                    NotificationDevice.tenant_id == tenant_id,
                    NotificationDevice.fcm_token == fcm_token,
                )
            )
        ).scalar_one()
        if row.user_id != user_id:
            raise PermissionError("token registered to another user")
        row.status = "active"
        row.platform = platform
        if app_label is not None:
            row.app_label = app_label
        row.last_seen_at = now
        row.updated_at = now
        await session.flush()
        return RegisteredDevice(device=row, created=False)
    return RegisteredDevice(device=device, created=True)


async def revoke_fcm_device(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    device_id: UUID,
) -> None:
    device = await session.get(NotificationDevice, device_id)
    if device is None or device.tenant_id != tenant_id or device.user_id != user_id:
        raise LookupError("device not found")
    device.status = "revoked"
    device.updated_at = datetime.now(UTC)
    await session.flush()


async def unregister_fcm_device_by_token(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    fcm_token: str,
) -> bool:
    """Revoke the caller's device row for ``fcm_token``. Returns True if found."""
    device = (
        await session.execute(
            select(NotificationDevice).where(
                NotificationDevice.tenant_id == tenant_id,
                NotificationDevice.user_id == user_id,
                NotificationDevice.fcm_token == fcm_token,
            )
        )
    ).scalar_one_or_none()
    if device is None:
        return False
    device.status = "revoked"
    device.updated_at = datetime.now(UTC)
    await session.flush()
    return True


async def list_active_devices_for_user(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
) -> list[NotificationDevice]:
    result = await session.execute(
        select(NotificationDevice).where(
            NotificationDevice.tenant_id == tenant_id,
            NotificationDevice.user_id == user_id,
            NotificationDevice.status == "active",
        )
    )
    return list(result.scalars())
