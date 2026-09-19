from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.cards.models import CardAssignment, PhysicalCard
from schoolpass.cards.normalize import normalize_hf_uid, normalize_uhf_epc, normalize_uhf_tid

RESOLUTION_RESOLVED = "resolved"
RESOLUTION_UNKNOWN = "unknown_card"
RESOLUTION_BLOCKED = "blocked_card"
RESOLUTION_RETIRED = "retired_card"
RESOLUTION_UNASSIGNED = "unassigned_card"
RESOLUTION_INVALID = "invalid_identifier"


@dataclass(frozen=True)
class CardResolution:
    resolution_status: str
    physical_card_id: UUID | None = None
    assignment_id: UUID | None = None
    student_id: UUID | None = None


async def find_physical_card(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    hf_uid: str | None,
    uhf_epc: str | None,
    uhf_tid: str | None,
) -> PhysicalCard | None:
    hf = normalize_hf_uid(hf_uid)
    epc = normalize_uhf_epc(uhf_epc)
    tid = normalize_uhf_tid(uhf_tid)
    if not hf and not epc and not tid:
        return None
    stmt = select(PhysicalCard).where(PhysicalCard.tenant_id == tenant_id)
    if epc:
        stmt = stmt.where(PhysicalCard.uhf_epc == epc)
    elif tid:
        stmt = stmt.where(PhysicalCard.uhf_tid == tid)
    elif hf:
        stmt = stmt.where(PhysicalCard.hf_uid == hf)
    result = await session.execute(stmt.limit(1))
    return result.scalar_one_or_none()


async def assignment_as_of(
    session: AsyncSession,
    tenant_id: UUID,
    physical_card_id: UUID,
    occurred_at: datetime,
) -> CardAssignment | None:
    stmt = (
        select(CardAssignment)
        .where(
            CardAssignment.tenant_id == tenant_id,
            CardAssignment.physical_card_id == physical_card_id,
            CardAssignment.issued_at <= occurred_at,
            CardAssignment.activated_at.is_not(None),
            CardAssignment.activated_at <= occurred_at,
            or_(CardAssignment.revoked_at.is_(None), CardAssignment.revoked_at > occurred_at),
        )
        .order_by(CardAssignment.activated_at.desc(), CardAssignment.id.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def resolve_card(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    hf_uid: str | None,
    uhf_epc: str | None,
    uhf_tid: str | None,
    occurred_at: datetime,
) -> CardResolution:
    card = await find_physical_card(
        session,
        tenant_id,
        hf_uid=hf_uid,
        uhf_epc=uhf_epc,
        uhf_tid=uhf_tid,
    )
    if card is None:
        return CardResolution(resolution_status=RESOLUTION_UNKNOWN)
    if card.status == "blocked":
        return CardResolution(resolution_status=RESOLUTION_BLOCKED, physical_card_id=card.id)
    if card.status == "retired":
        return CardResolution(resolution_status=RESOLUTION_RETIRED, physical_card_id=card.id)
    assignment = await assignment_as_of(session, tenant_id, card.id, occurred_at)
    if assignment is None:
        return CardResolution(resolution_status=RESOLUTION_UNASSIGNED, physical_card_id=card.id)
    return CardResolution(
        resolution_status=RESOLUTION_RESOLVED,
        physical_card_id=card.id,
        assignment_id=assignment.id,
        student_id=assignment.student_id,
    )
