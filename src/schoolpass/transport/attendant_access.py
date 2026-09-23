"""Transport attendant identity for mobile bus-attendant flows."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.errors import AuthenticationError, NotFoundError
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.models import TransportAttendant


async def load_active_transport_attendant(
    session: AsyncSession,
    ctx: TenantContext,
) -> TransportAttendant:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    row = (
        await session.execute(
            select(TransportAttendant).where(
                TransportAttendant.tenant_id == ctx.tenant_id,
                TransportAttendant.user_id == ctx.user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None or row.status != "active":
        raise AuthenticationError("Transport attendant profile required")
    return row


async def load_active_transport_attendant_for_tenant(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
) -> TransportAttendant:
    row = (
        await session.execute(
            select(TransportAttendant).where(
                TransportAttendant.tenant_id == tenant_id,
                TransportAttendant.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None or row.status != "active":
        raise AuthenticationError("Transport attendant profile required")
    return row
