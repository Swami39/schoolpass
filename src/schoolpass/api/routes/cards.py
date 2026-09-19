from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.cards import schemas as s
from schoolpass.cards import services as svc
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import ValidationFailed
from schoolpass.people.pagination import decode_cursor
from schoolpass.tenancy.context import TenantContext

router = APIRouter(prefix="/api/v1", tags=["cards"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


@router.post("/cards", response_model=s.CardResponse)
async def create_card(
    body: s.CardCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("cards:create"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.CardResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.register_card(
                session,
                _ctx(principal),
                hf_uid=body.hf_uid,
                uhf_epc=body.uhf_epc,
                uhf_tid=body.uhf_tid,
                profile=body.profile,
                manufactured_at=body.manufactured_at,
                request_id=_request_id(request),
            )
    return s.CardResponse.model_validate(row, from_attributes=True)


@router.get("/cards/{card_id}", response_model=s.CardResponse)
async def get_card(
    card_id: UUID,
    principal: Annotated[Principal, Depends(require("cards:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.CardResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_card(session, _ctx(principal), card_id)
    return s.CardResponse.model_validate(row, from_attributes=True)


@router.get("/cards", response_model=s.CardListResponse)
async def list_cards(
    principal: Annotated[Principal, Depends(require("cards:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    status: str | None = None,
    hf_uid: str | None = None,
    uhf_epc: str | None = None,
    uhf_tid: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> s.CardListResponse:
    if cursor:
        try:
            decode_cursor(cursor)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await svc.list_cards(
                session,
                _ctx(principal),
                status=status,
                hf_uid=hf_uid,
                uhf_epc=uhf_epc,
                uhf_tid=uhf_tid,
                limit=limit,
                cursor=cursor,
            )
    return s.CardListResponse(
        items=[s.CardResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.patch("/cards/{card_id}", response_model=s.CardResponse)
async def patch_card(
    card_id: UUID,
    body: s.CardUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require("cards:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.CardResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_card(session, _ctx(principal), card_id)
            if row.status != "inventory":
                raise ValidationFailed("Only inventory cards allow metadata updates")
            if body.manufactured_at is not None:
                row.manufactured_at = body.manufactured_at
            await session.flush()
    return s.CardResponse.model_validate(row, from_attributes=True)


@router.post("/cards/{card_id}/activate", response_model=s.CardResponse)
async def activate_card(
    card_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("cards:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.CardResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.transition_card_status(
                session,
                _ctx(principal),
                card_id,
                new_status="active",
                request_id=_request_id(request),
                audit_action="card.activated",
                outbox_topic="card.updated",
            )
    return s.CardResponse.model_validate(row, from_attributes=True)


@router.post("/cards/{card_id}/block", response_model=s.CardResponse)
async def block_card(
    card_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("cards:block"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.CardResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.transition_card_status(
                session,
                _ctx(principal),
                card_id,
                new_status="blocked",
                request_id=_request_id(request),
                audit_action="card.blocked",
                outbox_topic="card.blocked",
            )
    return s.CardResponse.model_validate(row, from_attributes=True)


@router.post("/cards/{card_id}/retire", response_model=s.CardResponse)
async def retire_card(
    card_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("cards:retire"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.CardResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.transition_card_status(
                session,
                _ctx(principal),
                card_id,
                new_status="retired",
                request_id=_request_id(request),
                audit_action="card.retired",
                outbox_topic="card.retired",
            )
    return s.CardResponse.model_validate(row, from_attributes=True)


@router.post("/card-assignments", response_model=s.AssignmentResponse)
async def create_assignment(
    body: s.AssignmentCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("card_assignments:create"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.create_assignment(
                session,
                _ctx(principal),
                student_id=body.student_id,
                physical_card_id=body.physical_card_id,
                request_id=_request_id(request),
            )
    return s.AssignmentResponse.model_validate(row, from_attributes=True)


@router.get("/card-assignments/{assignment_id}", response_model=s.AssignmentResponse)
async def get_assignment(
    assignment_id: UUID,
    principal: Annotated[Principal, Depends(require("card_assignments:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_assignment(session, _ctx(principal), assignment_id)
    return s.AssignmentResponse.model_validate(row, from_attributes=True)


@router.get("/students/{student_id}/cards", response_model=s.AssignmentListResponse)
async def student_cards(
    student_id: UUID,
    principal: Annotated[Principal, Depends(require("card_assignments:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AssignmentListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await svc.list_student_assignments(session, _ctx(principal), student_id)
    return s.AssignmentListResponse(
        items=[s.AssignmentResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=None,
    )


@router.get("/cards/{card_id}/assignments", response_model=s.AssignmentListResponse)
async def card_assignments(
    card_id: UUID,
    principal: Annotated[Principal, Depends(require("card_assignments:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AssignmentListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await svc.list_card_assignments(session, _ctx(principal), card_id)
    return s.AssignmentListResponse(
        items=[s.AssignmentResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=None,
    )


@router.post("/card-assignments/{assignment_id}/activate", response_model=s.AssignmentResponse)
async def activate_assignment(
    assignment_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("card_assignments:activate"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.activate_assignment(
                session, _ctx(principal), assignment_id, request_id=_request_id(request)
            )
    return s.AssignmentResponse.model_validate(row, from_attributes=True)


@router.post("/card-assignments/{assignment_id}/block", response_model=s.AssignmentResponse)
async def block_assignment(
    assignment_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("card_assignments:block"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.block_assignment(session, _ctx(principal), assignment_id, request_id=_request_id(request))
    return s.AssignmentResponse.model_validate(row, from_attributes=True)


@router.post("/card-assignments/{assignment_id}/mark-lost", response_model=s.AssignmentResponse)
async def mark_lost(
    assignment_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("card_assignments:lost"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.mark_lost_assignment(
                session, _ctx(principal), assignment_id, request_id=_request_id(request)
            )
    return s.AssignmentResponse.model_validate(row, from_attributes=True)


@router.post("/card-assignments/{assignment_id}/revoke", response_model=s.AssignmentResponse)
async def revoke_assignment(
    assignment_id: UUID,
    body: s.RevokeRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require("card_assignments:revoke"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.revoke_assignment(
                session,
                _ctx(principal),
                assignment_id,
                reason=body.reason,
                request_id=_request_id(request),
            )
    return s.AssignmentResponse.model_validate(row, from_attributes=True)


@router.post("/card-assignments/{assignment_id}/replace", response_model=s.AssignmentResponse)
async def replace_assignment(
    assignment_id: UUID,
    body: s.ReplaceRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require("card_assignments:replace"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.AssignmentResponse:
    new_fields = None
    if body.new_card is not None:
        new_fields = {
            "hf_uid": body.new_card.hf_uid,
            "uhf_epc": body.new_card.uhf_epc,
            "uhf_tid": body.new_card.uhf_tid,
            "profile": body.new_card.profile,
            "manufactured_at": body.new_card.manufactured_at,
        }
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.replace_assignment(
                session,
                _ctx(principal),
                assignment_id,
                new_physical_card_id=body.physical_card_id,
                new_card_fields=new_fields,
                activate=body.activate,
                revoke_reason=body.revoke_reason,
                request_id=_request_id(request),
            )
    return s.AssignmentResponse.model_validate(row, from_attributes=True)
