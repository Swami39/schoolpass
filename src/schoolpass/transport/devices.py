"""Bus-attendant client device registration for transport NFC/GPS sync."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.errors import NotFoundError
from schoolpass.identity.models import ClientDevice
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.attendant_access import load_active_transport_attendant


async def register_transport_attendant_client_device(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    device_uuid: UUID,
) -> ClientDevice:
    if ctx.user_id is None or ctx.tenant_id is None:
        raise NotFoundError()
    await load_active_transport_attendant(session, ctx)
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
        app_flavor="bus_attendant",
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
