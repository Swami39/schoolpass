from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.cards.models import CardAssignment, PhysicalCard
from schoolpass.errors import ValidationFailed
from schoolpass.rfid.models import RfidEvent
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.lifecycle import ACTIVE_TRIP_STATUSES, BUS_OPERATIONAL_STATUS
from schoolpass.transport.models import (
    Bus,
    TransportAssignment,
    TransportBoardingRecord,
    Trip,
)


def _tenant_id(ctx: TenantContext) -> UUID:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    return ctx.tenant_id


async def operations_overview(session: AsyncSession, ctx: TenantContext) -> dict[str, int]:
    tenant_id = _tenant_id(ctx)
    since = datetime.now(UTC) - timedelta(hours=24)

    active_buses = (
        await session.execute(
            select(func.count()).select_from(Bus).where(
                Bus.tenant_id == tenant_id,
                Bus.status == BUS_OPERATIONAL_STATUS,
            )
        )
    ).scalar_one()

    active_trips = (
        await session.execute(
            select(func.count()).select_from(Trip).where(
                Trip.tenant_id == tenant_id,
                Trip.status.in_(tuple(ACTIVE_TRIP_STATUSES)),
            )
        )
    ).scalar_one()

    active_transport_assignments = (
        await session.execute(
            select(func.count()).select_from(TransportAssignment).where(
                TransportAssignment.tenant_id == tenant_id,
                TransportAssignment.status == "active",
            )
        )
    ).scalar_one()

    active_card_assignments = (
        await session.execute(
            select(func.count()).select_from(CardAssignment).where(
                CardAssignment.tenant_id == tenant_id,
                CardAssignment.status == "active",
            )
        )
    ).scalar_one()

    pending_card_assignments = (
        await session.execute(
            select(func.count()).select_from(CardAssignment).where(
                CardAssignment.tenant_id == tenant_id,
                CardAssignment.status == "pending",
            )
        )
    ).scalar_one()

    registered_cards = (
        await session.execute(
            select(func.count()).select_from(PhysicalCard).where(
                PhysicalCard.tenant_id == tenant_id,
                PhysicalCard.status.in_(("inventory", "active")),
            )
        )
    ).scalar_one()

    blocked_cards = (
        await session.execute(
            select(func.count()).select_from(PhysicalCard).where(
                PhysicalCard.tenant_id == tenant_id,
                PhysicalCard.status == "blocked",
            )
        )
    ).scalar_one()

    rfid_events_24h = (
        await session.execute(
            select(func.count()).select_from(RfidEvent).where(
                RfidEvent.tenant_id == tenant_id,
                RfidEvent.received_at >= since,
            )
        )
    ).scalar_one()

    boarding_events_24h = (
        await session.execute(
            select(func.count()).select_from(TransportBoardingRecord).where(
                TransportBoardingRecord.tenant_id == tenant_id,
                TransportBoardingRecord.received_at >= since,
            )
        )
    ).scalar_one()

    return {
        "active_buses": int(active_buses),
        "active_trips": int(active_trips),
        "active_transport_assignments": int(active_transport_assignments),
        "active_card_assignments": int(active_card_assignments),
        "pending_card_assignments": int(pending_card_assignments),
        "registered_cards": int(registered_cards),
        "blocked_cards": int(blocked_cards),
        "rfid_events_last_24h": int(rfid_events_24h),
        "boarding_events_last_24h": int(boarding_events_24h),
    }
