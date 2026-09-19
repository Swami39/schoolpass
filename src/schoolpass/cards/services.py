from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.audit.service import record_audit
from schoolpass.cards.lifecycle import (
    CARD_PROFILES,
    TERMINAL_ASSIGNMENT_STATUSES,
    assert_card_status_transition,
)
from schoolpass.cards.models import CardAssignment, PhysicalCard
from schoolpass.cards.normalize import normalize_hf_uid, normalize_uhf_epc, normalize_uhf_tid
from schoolpass.db.mixins import utcnow
from schoolpass.errors import ConflictError, NotFoundError, ValidationFailed
from schoolpass.outbox.service import enqueue_outbox
from schoolpass.people.models import Student
from schoolpass.people.pagination import decode_cursor, encode_cursor
from schoolpass.tenancy.context import TenantContext

MAX_PAGE_SIZE = 200


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


async def _outbox(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    topic: str,
    idempotency_key: str,
    payload: dict[str, Any],
    request_id: str | None,
) -> None:
    await enqueue_outbox(
        session,
        topic=topic,
        idempotency_key=idempotency_key,
        tenant_id=ctx.tenant_id,
        correlation_id=request_id,
        payload=payload,
    )


def _require_tenant(ctx: TenantContext) -> UUID:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    return ctx.tenant_id


async def register_card(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    hf_uid: str | None,
    uhf_epc: str | None,
    uhf_tid: str | None,
    profile: str,
    manufactured_at: datetime | None,
    request_id: str | None,
) -> PhysicalCard:
    tenant_id = _require_tenant(ctx)
    if profile not in CARD_PROFILES:
        raise ValidationFailed("Invalid card profile")
    row = PhysicalCard(
        tenant_id=tenant_id,
        hf_uid=normalize_hf_uid(hf_uid),
        uhf_epc=normalize_uhf_epc(uhf_epc),
        uhf_tid=normalize_uhf_tid(uhf_tid),
        profile=profile,
        status="inventory",
        manufactured_at=manufactured_at,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Card identifier already registered") from exc
    await _audit(
        session,
        ctx,
        action="card.created",
        resource_type="physical_card",
        resource_id=row.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic="card.created",
        idempotency_key=f"card.created:{row.id}",
        payload={"card_id": str(row.id)},
        request_id=request_id,
    )
    return row


async def get_card(session: AsyncSession, ctx: TenantContext, card_id: UUID) -> PhysicalCard:
    row = await session.get(PhysicalCard, card_id)
    if row is None:
        raise NotFoundError()
    return row


async def list_cards(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    status: str | None,
    hf_uid: str | None,
    uhf_epc: str | None,
    uhf_tid: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[PhysicalCard], str | None]:
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    stmt = select(PhysicalCard).order_by(PhysicalCard.created_at.desc(), PhysicalCard.id.desc())
    if status:
        stmt = stmt.where(PhysicalCard.status == status)
    if hf_uid:
        stmt = stmt.where(PhysicalCard.hf_uid == normalize_hf_uid(hf_uid))
    if uhf_epc:
        stmt = stmt.where(PhysicalCard.uhf_epc == normalize_uhf_epc(uhf_epc))
    if uhf_tid:
        stmt = stmt.where(PhysicalCard.uhf_tid == normalize_uhf_tid(uhf_tid))
    decoded = decode_cursor(cursor) if cursor else None
    if decoded:
        created_at, row_id = decoded
        stmt = stmt.where(
            or_(
                PhysicalCard.created_at < created_at,
                and_(PhysicalCard.created_at == created_at, PhysicalCard.id < row_id),
            )
        )
    stmt = stmt.limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(created_at=last.created_at, row_id=last.id)
        rows = rows[:limit]
    return rows, next_cursor


async def transition_card_status(
    session: AsyncSession,
    ctx: TenantContext,
    card_id: UUID,
    *,
    new_status: str,
    request_id: str | None,
    audit_action: str,
    outbox_topic: str,
) -> PhysicalCard:
    row = await get_card(session, ctx, card_id)
    try:
        assert_card_status_transition(row.status, new_status)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
    row.status = new_status
    await session.flush()
    await _audit(
        session,
        ctx,
        action=audit_action,
        resource_type="physical_card",
        resource_id=row.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic=outbox_topic,
        idempotency_key=f"{outbox_topic}:{row.id}:{row.updated_at.isoformat()}",
        payload={"card_id": str(row.id)},
        request_id=request_id,
    )
    return row


async def create_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    student_id: UUID,
    physical_card_id: UUID,
    request_id: str | None,
) -> CardAssignment:
    tenant_id = _require_tenant(ctx)
    if await session.get(Student, student_id) is None:
        raise NotFoundError()
    card = await get_card(session, ctx, physical_card_id)
    if card.status == "retired":
        raise ValidationFailed("Retired cards cannot be assigned")
    row = CardAssignment(
        tenant_id=tenant_id,
        student_id=student_id,
        physical_card_id=physical_card_id,
        status="pending",
        issued_at=utcnow(),
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Assignment could not be created") from exc
    await _audit(
        session,
        ctx,
        action="card_assignment.created",
        resource_type="card_assignment",
        resource_id=row.id,
        request_id=request_id,
        metadata={"student_id": str(student_id), "card_id": str(physical_card_id)},
    )
    await _outbox(
        session,
        ctx,
        topic="card_assignment.created",
        idempotency_key=f"card_assignment.created:{row.id}",
        payload={
            "assignment_id": str(row.id),
            "student_id": str(student_id),
            "card_id": str(physical_card_id),
        },
        request_id=request_id,
    )
    return row


async def get_assignment(session: AsyncSession, ctx: TenantContext, assignment_id: UUID) -> CardAssignment:
    row = await session.get(CardAssignment, assignment_id)
    if row is None:
        raise NotFoundError()
    return row


async def list_student_assignments(
    session: AsyncSession,
    ctx: TenantContext,
    student_id: UUID,
) -> list[CardAssignment]:
    if await session.get(Student, student_id) is None:
        raise NotFoundError()
    result = await session.execute(
        select(CardAssignment)
        .where(CardAssignment.student_id == student_id)
        .order_by(CardAssignment.issued_at.desc(), CardAssignment.created_at.desc())
    )
    return list(result.scalars())


async def list_card_assignments(
    session: AsyncSession,
    ctx: TenantContext,
    card_id: UUID,
) -> list[CardAssignment]:
    await get_card(session, ctx, card_id)
    result = await session.execute(
        select(CardAssignment)
        .where(CardAssignment.physical_card_id == card_id)
        .order_by(CardAssignment.issued_at.desc(), CardAssignment.created_at.desc())
    )
    return list(result.scalars())


def _assert_assignment_mutable(row: CardAssignment) -> None:
    if row.status in TERMINAL_ASSIGNMENT_STATUSES:
        raise ConflictError("Assignment history is immutable")


async def activate_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    assignment_id: UUID,
    *,
    request_id: str | None,
) -> CardAssignment:
    row = await get_assignment(session, ctx, assignment_id)
    if row.status != "pending":
        raise ValidationFailed("Only pending assignments can be activated")
    card = await get_card(session, ctx, row.physical_card_id)
    if card.status in {"retired", "blocked"}:
        raise ValidationFailed("Card cannot be activated for assignment")
    now = utcnow()
    row.status = "active"
    row.activated_at = now
    if card.status == "inventory":
        card.status = "active"
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Student or card already has an active assignment") from exc
    await _audit(
        session,
        ctx,
        action="card_assignment.activated",
        resource_type="card_assignment",
        resource_id=row.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic="card_assignment.activated",
        idempotency_key=f"card_assignment.activated:{row.id}",
        payload={"assignment_id": str(row.id), "student_id": str(row.student_id), "card_id": str(row.physical_card_id)},
        request_id=request_id,
    )
    return row


async def _close_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    assignment_id: UUID,
    *,
    status: str,
    reason: str | None,
    request_id: str | None,
    audit_action: str,
    outbox_topic: str,
) -> CardAssignment:
    row = await get_assignment(session, ctx, assignment_id)
    if row.status != "active":
        raise ValidationFailed("Only active assignments support this operation")
    row.status = status
    row.revoked_at = utcnow()
    row.revoke_reason = reason
    await session.flush()
    await _audit(
        session,
        ctx,
        action=audit_action,
        resource_type="card_assignment",
        resource_id=row.id,
        request_id=request_id,
    )
    await _outbox(
        session,
        ctx,
        topic=outbox_topic,
        idempotency_key=f"{outbox_topic}:{row.id}",
        payload={"assignment_id": str(row.id), "student_id": str(row.student_id), "card_id": str(row.physical_card_id)},
        request_id=request_id,
    )
    return row


async def block_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    assignment_id: UUID,
    *,
    request_id: str | None,
) -> CardAssignment:
    return await _close_assignment(
        session,
        ctx,
        assignment_id,
        status="blocked",
        reason="blocked",
        request_id=request_id,
        audit_action="card_assignment.blocked",
        outbox_topic="card_assignment.blocked",
    )


async def mark_lost_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    assignment_id: UUID,
    *,
    request_id: str | None,
) -> CardAssignment:
    return await _close_assignment(
        session,
        ctx,
        assignment_id,
        status="lost",
        reason="lost",
        request_id=request_id,
        audit_action="card_assignment.lost",
        outbox_topic="card_assignment.lost",
    )


async def revoke_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    assignment_id: UUID,
    *,
    reason: str,
    request_id: str | None,
) -> CardAssignment:
    return await _close_assignment(
        session,
        ctx,
        assignment_id,
        status="revoked",
        reason=reason,
        request_id=request_id,
        audit_action="card_assignment.revoked",
        outbox_topic="card_assignment.revoked",
    )


async def replace_assignment(
    session: AsyncSession,
    ctx: TenantContext,
    assignment_id: UUID,
    *,
    new_physical_card_id: UUID | None,
    new_card_fields: dict[str, Any] | None,
    activate: bool,
    revoke_reason: str,
    request_id: str | None,
) -> CardAssignment:
    old = await get_assignment(session, ctx, assignment_id)
    if old.status != "active":
        raise ValidationFailed("Only active assignments can be replaced")
    if new_physical_card_id is None:
        if not new_card_fields:
            raise ValidationFailed("Replacement requires a physical card")
        card = await register_card(
            session,
            ctx,
            hf_uid=new_card_fields.get("hf_uid"),
            uhf_epc=new_card_fields.get("uhf_epc"),
            uhf_tid=new_card_fields.get("uhf_tid"),
            profile=str(new_card_fields.get("profile") or "uid_only"),
            manufactured_at=new_card_fields.get("manufactured_at"),
            request_id=request_id,
        )
        new_physical_card_id = card.id
    new_row = await create_assignment(
        session,
        ctx,
        student_id=old.student_id,
        physical_card_id=new_physical_card_id,
        request_id=request_id,
    )
    old.status = "replaced"
    old.revoked_at = utcnow()
    old.revoke_reason = revoke_reason
    old.replaced_by_assignment_id = new_row.id
    await session.flush()
    if activate:
        new_row = await activate_assignment(session, ctx, new_row.id, request_id=request_id)
    await _audit(
        session,
        ctx,
        action="card_assignment.replaced",
        resource_type="card_assignment",
        resource_id=old.id,
        request_id=request_id,
        metadata={"replacement_assignment_id": str(new_row.id)},
    )
    await _outbox(
        session,
        ctx,
        topic="card_assignment.replaced",
        idempotency_key=f"card_assignment.replaced:{old.id}:{new_row.id}",
        payload={
            "assignment_id": str(old.id),
            "replacement_assignment_id": str(new_row.id),
            "student_id": str(old.student_id),
        },
        request_id=request_id,
    )
    return new_row
