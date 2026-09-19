from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.admin import operations_schemas as aos
from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.api.routes.admin import _ctx, _request_id
from schoolpass.cards import services as card_svc
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import ValidationFailed
from schoolpass.people.pagination import decode_cursor
from schoolpass.rfid import schemas as rfid_schemas
from schoolpass.rfid import services as rfid_svc
from schoolpass.rfid.models import RfidEvent, RfidEventProcessing, RfidObservation
from schoolpass.transport import services as transport_svc

router = APIRouter(prefix="/api/v1/admin", tags=["admin-operations"])


def _event_response(
    event: RfidEvent,
    processing: RfidEventProcessing | None,
    observation: RfidObservation | None,
) -> rfid_schemas.RfidEventResponse:
    return rfid_schemas.RfidEventResponse(
        id=event.id,
        tenant_id=event.tenant_id,
        reader_id=event.reader_id,
        device_uuid=event.device_uuid,
        physical_card_id=event.physical_card_id,
        student_id=event.student_id,
        hf_uid=event.hf_uid,
        uhf_epc=event.uhf_epc,
        uhf_tid=event.uhf_tid,
        antenna=event.antenna,
        rssi=float(event.rssi) if event.rssi is not None else None,
        direction=event.direction,
        occurred_at=event.occurred_at,
        received_at=event.received_at,
        ingest_status=event.ingest_status,
        processing_status=processing.status if processing is not None else None,
        resolution_status=observation.resolution_status if observation is not None else None,
    )


# --- Cards ---


@router.get("/cards", response_model=aos.CardListResponse)
async def admin_list_cards(
    principal: Annotated[Principal, Depends(require("operations:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    status: str | None = None,
    hf_uid: str | None = None,
    uhf_epc: str | None = None,
    uhf_tid: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> aos.CardListResponse:
    if cursor:
        try:
            decode_cursor(cursor)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await card_svc.list_cards(
                session,
                _ctx(principal),
                status=status,
                hf_uid=hf_uid,
                uhf_epc=uhf_epc,
                uhf_tid=uhf_tid,
                limit=limit,
                cursor=cursor,
            )
    return aos.CardListResponse(
        items=[aos.CardResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.get("/cards/{card_id}", response_model=aos.CardResponse)
async def admin_get_card(
    card_id: UUID,
    principal: Annotated[Principal, Depends(require("operations:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> aos.CardResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await card_svc.get_card(session, _ctx(principal), card_id)
    return aos.CardResponse.model_validate(row, from_attributes=True)


@router.post("/cards", response_model=aos.CardResponse)
async def admin_create_card(
    request: Request,
    body: aos.AdminCardCreate,
    principal: Annotated[Principal, Depends(require("operations:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> aos.CardResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await card_svc.register_card(
                session,
                _ctx(principal),
                hf_uid=body.hf_uid,
                uhf_epc=body.uhf_epc,
                uhf_tid=body.uhf_tid,
                profile=body.profile,
                manufactured_at=body.manufactured_at,
                request_id=_request_id(request),
            )
    return aos.CardResponse.model_validate(row, from_attributes=True)


@router.post("/cards/{card_id}/block", response_model=aos.CardResponse)
async def admin_block_card(
    request: Request,
    card_id: UUID,
    principal: Annotated[Principal, Depends(require("operations:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> aos.CardResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await card_svc.transition_card_status(
                session,
                _ctx(principal),
                card_id,
                new_status="blocked",
                request_id=_request_id(request),
                audit_action="card.blocked",
                outbox_topic="card.blocked",
            )
    return aos.CardResponse.model_validate(row, from_attributes=True)


@router.get("/students/{student_id}/card-assignments", response_model=aos.AssignmentListResponse)
async def admin_student_card_assignments(
    student_id: UUID,
    principal: Annotated[Principal, Depends(require("operations:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> aos.AssignmentListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await card_svc.list_student_assignments(session, _ctx(principal), student_id)
    return aos.AssignmentListResponse(
        items=[aos.AssignmentResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=None,
    )


@router.post("/card-assignments", response_model=aos.AssignmentResponse)
async def admin_create_assignment(
    request: Request,
    body: aos.AdminAssignmentCreate,
    principal: Annotated[Principal, Depends(require("operations:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> aos.AssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await card_svc.create_assignment(
                session,
                _ctx(principal),
                student_id=body.student_id,
                physical_card_id=body.physical_card_id,
                request_id=_request_id(request),
            )
    return aos.AssignmentResponse.model_validate(row, from_attributes=True)


@router.post("/card-assignments/{assignment_id}/activate", response_model=aos.AssignmentResponse)
async def admin_activate_assignment(
    request: Request,
    assignment_id: UUID,
    principal: Annotated[Principal, Depends(require("operations:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> aos.AssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await card_svc.activate_assignment(
                session, _ctx(principal), assignment_id, request_id=_request_id(request)
            )
    return aos.AssignmentResponse.model_validate(row, from_attributes=True)


@router.post("/card-assignments/{assignment_id}/replace", response_model=aos.AssignmentResponse)
async def admin_replace_assignment(
    request: Request,
    assignment_id: UUID,
    body: aos.AdminReplaceAssignment,
    principal: Annotated[Principal, Depends(require("operations:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> aos.AssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await card_svc.replace_assignment(
                session,
                _ctx(principal),
                assignment_id,
                new_physical_card_id=body.physical_card_id,
                new_card_fields=None,
                activate=body.activate,
                revoke_reason=body.revoke_reason,
                request_id=_request_id(request),
            )
    return aos.AssignmentResponse.model_validate(row, from_attributes=True)


@router.post("/card-assignments/{assignment_id}/revoke", response_model=aos.AssignmentResponse)
async def admin_revoke_assignment(
    request: Request,
    assignment_id: UUID,
    body: aos.AdminRevokeAssignment,
    principal: Annotated[Principal, Depends(require("operations:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> aos.AssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await card_svc.revoke_assignment(
                session,
                _ctx(principal),
                assignment_id,
                reason=body.reason,
                request_id=_request_id(request),
            )
    return aos.AssignmentResponse.model_validate(row, from_attributes=True)


# --- RFID ---


@router.get("/rfid-readers", response_model=rfid_schemas.RfidReaderListResponse)
async def admin_list_readers(
    principal: Annotated[Principal, Depends(require("operations:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> rfid_schemas.RfidReaderListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await rfid_svc.list_readers(session, _ctx(principal))
    return rfid_schemas.RfidReaderListResponse(
        items=[rfid_schemas.RfidReaderResponse.model_validate(r, from_attributes=True) for r in rows]
    )


@router.post("/rfid-readers", response_model=rfid_schemas.RfidReaderResponse)
async def admin_create_reader(
    request: Request,
    body: aos.AdminReaderCreate,
    principal: Annotated[Principal, Depends(require("operations:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> rfid_schemas.RfidReaderResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await rfid_svc.create_reader(
                session,
                _ctx(principal),
                name=body.name,
                location=body.location,
                gate_id=body.gate_id,
                direction_mode=body.direction_mode,
                request_id=_request_id(request),
            )
    return rfid_schemas.RfidReaderResponse.model_validate(row, from_attributes=True)


@router.patch("/rfid-readers/{reader_id}", response_model=rfid_schemas.RfidReaderResponse)
async def admin_patch_reader(
    request: Request,
    reader_id: UUID,
    body: aos.AdminReaderUpdate,
    principal: Annotated[Principal, Depends(require("operations:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> rfid_schemas.RfidReaderResponse:
    fields = body.model_dump(exclude_unset=True)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await rfid_svc.patch_reader(
                session,
                _ctx(principal),
                reader_id,
                name=fields.get("name"),
                location=fields.get("location"),
                gate_id=fields.get("gate_id"),
                direction_mode=fields.get("direction_mode"),
                status=fields.get("status"),
                request_id=_request_id(request),
            )
    return rfid_schemas.RfidReaderResponse.model_validate(row, from_attributes=True)


@router.get("/rfid-devices", response_model=rfid_schemas.RfidDeviceListResponse)
async def admin_list_devices(
    principal: Annotated[Principal, Depends(require("operations:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> rfid_schemas.RfidDeviceListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await rfid_svc.list_devices(session, _ctx(principal))
    return rfid_schemas.RfidDeviceListResponse(
        items=[rfid_schemas.RfidDeviceResponse.model_validate(r, from_attributes=True) for r in rows]
    )


@router.get("/rfid-events", response_model=rfid_schemas.RfidEventListResponse)
async def admin_list_rfid_events(
    principal: Annotated[Principal, Depends(require("operations:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    reader_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> rfid_schemas.RfidEventListResponse:
    if cursor:
        try:
            decode_cursor(cursor)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await rfid_svc.list_events(
                session,
                _ctx(principal),
                reader_id=reader_id,
                limit=limit,
                cursor=cursor,
            )
    return rfid_schemas.RfidEventListResponse(
        items=[_event_response(e, p, o) for e, p, o in rows],
        next_cursor=next_cursor,
    )


# --- Transport ---


@router.get("/buses", response_model=aos.BusListResponse)
async def admin_list_buses(
    principal: Annotated[Principal, Depends(require("operations:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    status: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> aos.BusListResponse:
    if cursor:
        try:
            decode_cursor(cursor)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await transport_svc.list_buses(
                session,
                _ctx(principal),
                status=status,
                search=search,
                limit=limit,
                cursor=cursor,
            )
    return aos.BusListResponse(
        items=[aos.BusResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.post("/buses", response_model=aos.BusResponse)
async def admin_create_bus(
    request: Request,
    body: aos.AdminBusCreate,
    principal: Annotated[Principal, Depends(require("operations:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> aos.BusResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await transport_svc.create_bus(
                session,
                _ctx(principal),
                registration_number=body.registration_number,
                fleet_number=body.fleet_number,
                display_name=body.display_name,
                capacity=body.capacity,
                request_id=_request_id(request),
            )
    return aos.BusResponse.model_validate(row, from_attributes=True)


@router.patch("/buses/{bus_id}", response_model=aos.BusResponse)
async def admin_patch_bus(
    request: Request,
    bus_id: UUID,
    body: aos.AdminBusUpdate,
    principal: Annotated[Principal, Depends(require("operations:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> aos.BusResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            fields = body.model_dump(exclude_unset=True)
            row = await transport_svc.update_bus(
                session,
                _ctx(principal),
                bus_id,
                fleet_number=fields.get("fleet_number"),
                display_name=fields.get("display_name"),
                capacity=fields.get("capacity"),
                request_id=_request_id(request),
            )
    return aos.BusResponse.model_validate(row, from_attributes=True)


@router.get("/trips", response_model=aos.TripListResponse)
async def admin_list_trips(
    principal: Annotated[Principal, Depends(require("operations:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    service_date: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> aos.TripListResponse:
    from datetime import date as date_type

    if cursor:
        try:
            decode_cursor(cursor)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc
    parsed_date = date_type.fromisoformat(service_date) if service_date else None
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await transport_svc.list_trips(
                session,
                _ctx(principal),
                service_date=parsed_date,
                bus_id=None,
                route_id=None,
                attendant_id=None,
                status=status,
                shift=None,
                limit=limit,
                cursor=cursor,
            )
    return aos.TripListResponse(
        items=[aos.TripResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.get("/transport-assignments", response_model=aos.TransportAssignmentListResponse)
async def admin_list_transport_assignments(
    principal: Annotated[Principal, Depends(require("operations:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    student_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> aos.TransportAssignmentListResponse:
    if cursor:
        try:
            decode_cursor(cursor)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await transport_svc.list_transport_assignments(
                session,
                _ctx(principal),
                student_id=student_id,
                route_id=None,
                status=status,
                effective_on=None,
                limit=limit,
                cursor=cursor,
            )
    return aos.TransportAssignmentListResponse(
        items=[aos.TransportAssignmentResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )
