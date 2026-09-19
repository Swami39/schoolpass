"""Teacher client device registration for NFC sync."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.errors import NotFoundError
from schoolpass.identity.models import ClientDevice
from schoolpass.teacher.access import load_teacher_staff
from schoolpass.tenancy.context import TenantContext


async def register_teacher_client_device(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    device_uuid: UUID,
) -> ClientDevice:
    if ctx.user_id is None or ctx.tenant_id is None:
        raise NotFoundError()
    await load_teacher_staff(session, tenant_id=ctx.tenant_id, user_id=ctx.user_id)
    existing = (
        await session.execute(
            select(ClientDevice).where(
                ClientDevice.user_id == ctx.user_id,
                ClientDevice.device_uuid == device_uuid,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.status != "active":
            existing.status = "active"
            await session.flush()
        return existing
    device = ClientDevice(
        user_id=ctx.user_id,
        device_uuid=device_uuid,
        app_flavor="teacher",
        status="active",
    )
    try:
        session.add(device)
        await session.flush()
    except IntegrityError:
        row = (
            await session.execute(
                select(ClientDevice).where(
                    ClientDevice.user_id == ctx.user_id,
                    ClientDevice.device_uuid == device_uuid,
                )
            )
        ).scalar_one()
        return row
    return device
