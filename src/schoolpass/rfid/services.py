from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.audit.service import record_audit
from schoolpass.auth.crypto import decrypt_secret, encrypt_secret
from schoolpass.config import Settings
from schoolpass.db.mixins import utcnow
from schoolpass.errors import ConflictError, NotFoundError, ValidationFailed
from schoolpass.rfid.models import RfidDevice, RfidDeviceKey, RfidReader
from schoolpass.rfid.security import generate_device_secret
from schoolpass.tenancy.context import TenantContext

READER_STATUSES = frozenset({"active", "blocked", "retired"})
DEVICE_STATUSES = frozenset({"active", "blocked", "retired"})


def _require_tenant(ctx: TenantContext) -> UUID:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    return ctx.tenant_id


async def _audit(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    action: str,
    resource_type: str,
    resource_id: UUID,
    request_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await record_audit(
        session,
        ctx,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        metadata=metadata or {},
    )


async def create_reader(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    name: str,
    location: str | None,
    gate_id: UUID | None,
    direction_mode: str | None,
    request_id: str | None,
) -> RfidReader:
    tenant_id = _require_tenant(ctx)
    row = RfidReader(
        tenant_id=tenant_id,
        name=name,
        location=location,
        gate_id=gate_id,
        direction_mode=direction_mode,
        status="active",
    )
    session.add(row)
    await session.flush()
    await _audit(
        session,
        ctx,
        action="rfid_reader.created",
        resource_type="rfid_reader",
        resource_id=row.id,
        request_id=request_id,
    )
    return row


async def get_reader(session: AsyncSession, ctx: TenantContext, reader_id: UUID) -> RfidReader:
    row = await session.get(RfidReader, reader_id)
    if row is None:
        raise NotFoundError()
    return row


async def list_readers(session: AsyncSession, ctx: TenantContext) -> list[RfidReader]:
    _require_tenant(ctx)
    result = await session.execute(select(RfidReader).order_by(RfidReader.created_at.desc()))
    return list(result.scalars())


async def patch_reader(
    session: AsyncSession,
    ctx: TenantContext,
    reader_id: UUID,
    *,
    name: str | None,
    location: str | None,
    gate_id: UUID | None,
    direction_mode: str | None,
    status: str | None,
    request_id: str | None,
) -> RfidReader:
    row = await get_reader(session, ctx, reader_id)
    if name is not None:
        row.name = name
    if location is not None:
        row.location = location
    if gate_id is not None:
        row.gate_id = gate_id
    if direction_mode is not None:
        row.direction_mode = direction_mode
    if status is not None:
        if status not in READER_STATUSES:
            raise ValidationFailed("Invalid reader status")
        row.status = status
        action = {
            "blocked": "rfid_reader.blocked",
            "retired": "rfid_reader.retired",
        }.get(status)
        if action:
            await _audit(
                session,
                ctx,
                action=action,
                resource_type="rfid_reader",
                resource_id=row.id,
                request_id=request_id,
            )
    row.updated_at = utcnow()
    await session.flush()
    return row


async def register_device(
    session: AsyncSession,
    ctx: TenantContext,
    settings: Settings,
    *,
    device_id: str,
    reader_id: UUID,
    device_name: str | None,
    request_id: str | None,
) -> tuple[RfidDevice, str]:
    tenant_id = _require_tenant(ctx)
    reader = await get_reader(session, ctx, reader_id)
    if reader.status != "active":
        raise ValidationFailed("Reader must be active to register a device")
    secret = generate_device_secret()
    device = RfidDevice(
        tenant_id=tenant_id,
        device_id=device_id,
        reader_id=reader_id,
        key_version=1,
        status="active",
        device_name=device_name,
    )
    session.add(device)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Device id already registered") from exc
    key = RfidDeviceKey(
        device_uuid=device.id,
        key_version=1,
        secret_encrypted=encrypt_secret(settings, secret),
        status="active",
        created_at=utcnow(),
    )
    session.add(key)
    await session.flush()
    await _audit(
        session,
        ctx,
        action="rfid_device.created",
        resource_type="rfid_device",
        resource_id=device.id,
        request_id=request_id,
        metadata={"device_id": device_id, "reader_id": str(reader_id)},
    )
    return device, secret


async def get_device(session: AsyncSession, ctx: TenantContext, device_uuid: UUID) -> RfidDevice:
    row = await session.get(RfidDevice, device_uuid)
    if row is None:
        raise NotFoundError()
    if ctx.tenant_id is not None and row.tenant_id != ctx.tenant_id:
        raise NotFoundError()
    return row


async def list_devices(session: AsyncSession, ctx: TenantContext) -> list[RfidDevice]:
    tenant_id = _require_tenant(ctx)
    result = await session.execute(
        select(RfidDevice).where(RfidDevice.tenant_id == tenant_id).order_by(RfidDevice.created_at.desc())
    )
    return list(result.scalars())


async def patch_device(
    session: AsyncSession,
    ctx: TenantContext,
    device_uuid: UUID,
    *,
    device_name: str | None,
    status: str | None,
    request_id: str | None,
) -> RfidDevice:
    row = await get_device(session, ctx, device_uuid)
    if device_name is not None:
        row.device_name = device_name
    if status is not None:
        if status not in DEVICE_STATUSES:
            raise ValidationFailed("Invalid device status")
        row.status = status
        action = {
            "blocked": "rfid_device.blocked",
            "retired": "rfid_device.retired",
        }.get(status)
        if action:
            await _audit(
                session,
                ctx,
                action=action,
                resource_type="rfid_device",
                resource_id=row.id,
                request_id=request_id,
            )
    row.updated_at = utcnow()
    await session.flush()
    return row


async def rotate_device_key(
    session: AsyncSession,
    ctx: TenantContext,
    settings: Settings,
    device_uuid: UUID,
    *,
    request_id: str | None,
) -> tuple[RfidDevice, str]:
    device = await get_device(session, ctx, device_uuid)
    if device.status != "active":
        raise ValidationFailed("Device must be active to rotate keys")
    new_version = device.key_version + 1
    secret = generate_device_secret()
    result = await session.execute(
        select(RfidDeviceKey).where(
            RfidDeviceKey.device_uuid == device.id,
            RfidDeviceKey.key_version == device.key_version,
            RfidDeviceKey.status == "active",
        )
    )
    current = result.scalar_one_or_none()
    if current is not None:
        current.status = "revoked"
        current.revoked_at = utcnow()
    session.add(
        RfidDeviceKey(
            device_uuid=device.id,
            key_version=new_version,
            secret_encrypted=encrypt_secret(settings, secret),
            status="active",
            created_at=utcnow(),
        )
    )
    device.key_version = new_version
    device.updated_at = utcnow()
    await session.flush()
    await _audit(
        session,
        ctx,
        action="rfid_device.key_rotated",
        resource_type="rfid_device",
        resource_id=device.id,
        request_id=request_id,
        metadata={"key_version": new_version},
    )
    return device, secret


async def load_device_secret(
    session: AsyncSession,
    settings: Settings,
    device_uuid: UUID,
    key_version: int,
) -> str | None:
    result = await session.execute(
        select(RfidDeviceKey).where(
            RfidDeviceKey.device_uuid == device_uuid,
            RfidDeviceKey.key_version == key_version,
            RfidDeviceKey.status == "active",
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return decrypt_secret(settings, row.secret_encrypted)
