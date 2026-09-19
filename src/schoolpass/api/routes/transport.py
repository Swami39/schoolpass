from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import NotFoundError, ValidationFailed
from schoolpass.people.pagination import decode_cursor
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport import schemas as s
from schoolpass.transport import services as svc
from schoolpass.transport.models import RouteStop

router = APIRouter(prefix="/api/v1", tags=["transport"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


def _validate_cursor(cursor: str | None) -> None:
    if cursor:
        try:
            decode_cursor(cursor)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc


async def _route_stop_for_route(
    session: AsyncSession,
    ctx: TenantContext,
    route_id: UUID,
    stop_id: UUID,
) -> RouteStop:
    row = await svc.get_route_stop(session, ctx, stop_id)
    if row.route_id != route_id:
        raise NotFoundError()
    return row


@router.get("/buses", response_model=s.BusListResponse, summary="List buses")
async def list_buses(
    principal: Annotated[Principal, Depends(require("buses:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    status: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> s.BusListResponse:
    _validate_cursor(cursor)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await svc.list_buses(
                session,
                _ctx(principal),
                status=status,
                search=search,
                limit=limit,
                cursor=cursor,
            )
    return s.BusListResponse(
        items=[s.BusResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.post("/buses", response_model=s.BusResponse, summary="Register a bus")
async def create_bus(
    body: s.BusCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("buses:create"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.BusResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.create_bus(
                session,
                _ctx(principal),
                registration_number=body.registration_number,
                fleet_number=body.fleet_number,
                display_name=body.display_name,
                capacity=body.capacity,
                request_id=_request_id(request),
            )
    return s.BusResponse.model_validate(row, from_attributes=True)


@router.get("/buses/{bus_id}", response_model=s.BusResponse, summary="Get a bus")
async def get_bus(
    bus_id: UUID,
    principal: Annotated[Principal, Depends(require("buses:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.BusResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_bus(session, _ctx(principal), bus_id)
    return s.BusResponse.model_validate(row, from_attributes=True)


@router.patch("/buses/{bus_id}", response_model=s.BusResponse, summary="Update bus metadata")
async def patch_bus(
    bus_id: UUID,
    body: s.BusUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require("buses:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.BusResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.update_bus(
                session,
                _ctx(principal),
                bus_id,
                registration_number=body.registration_number,
                fleet_number=body.fleet_number,
                display_name=body.display_name,
                capacity=body.capacity,
                request_id=_request_id(request),
            )
    return s.BusResponse.model_validate(row, from_attributes=True)


@router.post("/buses/{bus_id}/retire", response_model=s.BusResponse, summary="Retire a bus")
async def retire_bus(
    bus_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("buses:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.BusResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.retire_bus(session, _ctx(principal), bus_id, request_id=_request_id(request))
    return s.BusResponse.model_validate(row, from_attributes=True)


@router.get(
    "/transport-attendants",
    response_model=s.TransportAttendantListResponse,
    summary="List transport attendants",
)
async def list_transport_attendants(
    principal: Annotated[Principal, Depends(require("transport_attendants:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> s.TransportAttendantListResponse:
    _validate_cursor(cursor)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await svc.list_transport_attendants(
                session,
                _ctx(principal),
                status=status,
                limit=limit,
                cursor=cursor,
            )
    return s.TransportAttendantListResponse(
        items=[s.TransportAttendantResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.post(
    "/transport-attendants",
    response_model=s.TransportAttendantResponse,
    summary="Create a transport attendant",
)
async def create_transport_attendant(
    body: s.TransportAttendantCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("transport_attendants:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TransportAttendantResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.create_transport_attendant(
                session,
                _ctx(principal),
                user_id=body.user_id,
                employee_code=body.employee_code,
                request_id=_request_id(request),
            )
    return s.TransportAttendantResponse.model_validate(row, from_attributes=True)


@router.get(
    "/transport-attendants/{attendant_id}",
    response_model=s.TransportAttendantResponse,
    summary="Get a transport attendant",
)
async def get_transport_attendant(
    attendant_id: UUID,
    principal: Annotated[Principal, Depends(require("transport_attendants:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TransportAttendantResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_transport_attendant(session, _ctx(principal), attendant_id)
    return s.TransportAttendantResponse.model_validate(row, from_attributes=True)


@router.patch(
    "/transport-attendants/{attendant_id}",
    response_model=s.TransportAttendantResponse,
    summary="Update a transport attendant",
)
async def patch_transport_attendant(
    attendant_id: UUID,
    body: s.TransportAttendantUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require("transport_attendants:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TransportAttendantResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.update_transport_attendant(
                session,
                _ctx(principal),
                attendant_id,
                employee_code=body.employee_code,
                request_id=_request_id(request),
            )
    return s.TransportAttendantResponse.model_validate(row, from_attributes=True)


@router.post(
    "/transport-attendants/{attendant_id}/activate",
    response_model=s.TransportAttendantResponse,
    summary="Activate a transport attendant",
)
async def activate_transport_attendant(
    attendant_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("transport_attendants:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TransportAttendantResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.activate_transport_attendant(
                session,
                _ctx(principal),
                attendant_id,
                request_id=_request_id(request),
            )
    return s.TransportAttendantResponse.model_validate(row, from_attributes=True)


@router.post(
    "/transport-attendants/{attendant_id}/deactivate",
    response_model=s.TransportAttendantResponse,
    summary="Deactivate a transport attendant",
)
async def deactivate_transport_attendant(
    attendant_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("transport_attendants:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TransportAttendantResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.deactivate_transport_attendant(
                session,
                _ctx(principal),
                attendant_id,
                request_id=_request_id(request),
            )
    return s.TransportAttendantResponse.model_validate(row, from_attributes=True)


@router.get("/routes", response_model=s.RouteListResponse, summary="List transport routes")
async def list_routes(
    principal: Annotated[Principal, Depends(require("routes:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    status: str | None = None,
    direction: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> s.RouteListResponse:
    _validate_cursor(cursor)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await svc.list_routes(
                session,
                _ctx(principal),
                status=status,
                direction=direction,
                search=search,
                limit=limit,
                cursor=cursor,
            )
    return s.RouteListResponse(
        items=[s.RouteResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.post("/routes", response_model=s.RouteResponse, summary="Create a transport route")
async def create_route(
    body: s.RouteCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("routes:create"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RouteResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.create_route(
                session,
                _ctx(principal),
                name=body.name,
                code=body.code,
                direction=body.direction,
                request_id=_request_id(request),
            )
    return s.RouteResponse.model_validate(row, from_attributes=True)


@router.get("/routes/{route_id}", response_model=s.RouteResponse, summary="Get a transport route")
async def get_route(
    route_id: UUID,
    principal: Annotated[Principal, Depends(require("routes:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RouteResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_route(session, _ctx(principal), route_id)
    return s.RouteResponse.model_validate(row, from_attributes=True)


@router.patch("/routes/{route_id}", response_model=s.RouteResponse, summary="Update a transport route")
async def patch_route(
    route_id: UUID,
    body: s.RouteUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require("routes:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RouteResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.update_route(
                session,
                _ctx(principal),
                route_id,
                name=body.name,
                code=body.code,
                direction=body.direction,
                request_id=_request_id(request),
            )
    return s.RouteResponse.model_validate(row, from_attributes=True)


@router.post("/routes/{route_id}/activate", response_model=s.RouteResponse, summary="Activate a route")
async def activate_route(
    route_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("routes:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RouteResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.activate_route(session, _ctx(principal), route_id, request_id=_request_id(request))
    return s.RouteResponse.model_validate(row, from_attributes=True)


@router.post("/routes/{route_id}/deactivate", response_model=s.RouteResponse, summary="Deactivate a route")
async def deactivate_route(
    route_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("routes:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RouteResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.deactivate_route(session, _ctx(principal), route_id, request_id=_request_id(request))
    return s.RouteResponse.model_validate(row, from_attributes=True)


@router.post("/routes/{route_id}/retire", response_model=s.RouteResponse, summary="Retire a route")
async def retire_route(
    route_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("routes:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RouteResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.retire_route(session, _ctx(principal), route_id, request_id=_request_id(request))
    return s.RouteResponse.model_validate(row, from_attributes=True)


@router.get(
    "/routes/{route_id}/stops",
    response_model=s.RouteStopListResponse,
    summary="List stops on a route",
)
async def list_route_stops(
    route_id: UUID,
    principal: Annotated[Principal, Depends(require("route_stops:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RouteStopListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await svc.list_route_stops(session, _ctx(principal), route_id)
    return s.RouteStopListResponse(
        items=[s.RouteStopResponse.model_validate(r, from_attributes=True) for r in rows],
    )


@router.post(
    "/routes/{route_id}/stops",
    response_model=s.RouteStopResponse,
    summary="Add a stop to a route",
)
async def create_route_stop(
    route_id: UUID,
    body: s.RouteStopCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("route_stops:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RouteStopResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.add_route_stop(
                session,
                _ctx(principal),
                route_id,
                name=body.name,
                sequence=body.sequence,
                latitude=body.latitude,
                longitude=body.longitude,
                geofence_radius_meters=body.geofence_radius_meters,
                request_id=_request_id(request),
            )
    return s.RouteStopResponse.model_validate(row, from_attributes=True)


@router.get(
    "/routes/{route_id}/stops/{stop_id}",
    response_model=s.RouteStopResponse,
    summary="Get a route stop",
)
async def get_route_stop(
    route_id: UUID,
    stop_id: UUID,
    principal: Annotated[Principal, Depends(require("route_stops:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RouteStopResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await _route_stop_for_route(session, _ctx(principal), route_id, stop_id)
    return s.RouteStopResponse.model_validate(row, from_attributes=True)


@router.patch(
    "/routes/{route_id}/stops/{stop_id}",
    response_model=s.RouteStopResponse,
    summary="Update a route stop",
)
async def patch_route_stop(
    route_id: UUID,
    stop_id: UUID,
    body: s.RouteStopUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require("route_stops:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RouteStopResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            await _route_stop_for_route(session, _ctx(principal), route_id, stop_id)
            row = await svc.update_route_stop(
                session,
                _ctx(principal),
                stop_id,
                name=body.name,
                sequence=body.sequence,
                latitude=body.latitude,
                longitude=body.longitude,
                geofence_radius_meters=body.geofence_radius_meters,
                request_id=_request_id(request),
            )
    return s.RouteStopResponse.model_validate(row, from_attributes=True)


@router.post(
    "/routes/{route_id}/stops/reorder",
    response_model=s.RouteStopListResponse,
    summary="Reorder route stops",
)
async def reorder_route_stops(
    route_id: UUID,
    body: s.RouteStopReorderRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require("route_stops:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RouteStopListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await svc.reorder_route_stops(
                session,
                _ctx(principal),
                route_id,
                ordered_stop_ids=body.stop_ids,
                request_id=_request_id(request),
            )
    return s.RouteStopListResponse(
        items=[s.RouteStopResponse.model_validate(r, from_attributes=True) for r in rows],
    )


@router.post(
    "/routes/{route_id}/stops/{stop_id}/deactivate",
    response_model=s.RouteStopResponse,
    summary="Deactivate a route stop",
)
async def deactivate_route_stop(
    route_id: UUID,
    stop_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("route_stops:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RouteStopResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            await _route_stop_for_route(session, _ctx(principal), route_id, stop_id)
            row = await svc.deactivate_route_stop(
                session,
                _ctx(principal),
                stop_id,
                request_id=_request_id(request),
            )
    return s.RouteStopResponse.model_validate(row, from_attributes=True)


@router.get(
    "/transport-assignments",
    response_model=s.TransportAssignmentListResponse,
    summary="List transport assignments",
)
async def list_transport_assignments(
    principal: Annotated[Principal, Depends(require("transport_assignments:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    student_id: UUID | None = None,
    route_id: UUID | None = None,
    status: str | None = None,
    effective_on: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> s.TransportAssignmentListResponse:
    _validate_cursor(cursor)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await svc.list_transport_assignments(
                session,
                _ctx(principal),
                student_id=student_id,
                route_id=route_id,
                status=status,
                effective_on=effective_on,
                limit=limit,
                cursor=cursor,
            )
    return s.TransportAssignmentListResponse(
        items=[s.TransportAssignmentResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.post(
    "/transport-assignments",
    response_model=s.TransportAssignmentResponse,
    summary="Create a transport assignment",
)
async def create_transport_assignment(
    body: s.TransportAssignmentCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("transport_assignments:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TransportAssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.create_transport_assignment(
                session,
                _ctx(principal),
                student_id=body.student_id,
                route_id=body.route_id,
                stop_id=body.stop_id,
                effective_from=body.effective_from,
                effective_to=body.effective_to,
                request_id=_request_id(request),
            )
    return s.TransportAssignmentResponse.model_validate(row, from_attributes=True)


@router.get(
    "/transport-assignments/{assignment_id}",
    response_model=s.TransportAssignmentResponse,
    summary="Get a transport assignment",
)
async def get_transport_assignment(
    assignment_id: UUID,
    principal: Annotated[Principal, Depends(require("transport_assignments:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TransportAssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_transport_assignment(session, _ctx(principal), assignment_id)
    return s.TransportAssignmentResponse.model_validate(row, from_attributes=True)


@router.patch(
    "/transport-assignments/{assignment_id}",
    response_model=s.TransportAssignmentResponse,
    summary="Update a transport assignment",
)
async def patch_transport_assignment(
    assignment_id: UUID,
    body: s.TransportAssignmentUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require("transport_assignments:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TransportAssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.update_transport_assignment(
                session,
                _ctx(principal),
                assignment_id,
                route_id=body.route_id,
                stop_id=body.stop_id,
                effective_from=body.effective_from,
                effective_to=body.effective_to,
                request_id=_request_id(request),
            )
    return s.TransportAssignmentResponse.model_validate(row, from_attributes=True)


@router.post(
    "/transport-assignments/{assignment_id}/suspend",
    response_model=s.TransportAssignmentResponse,
    summary="Suspend a transport assignment",
)
async def suspend_transport_assignment(
    assignment_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("transport_assignments:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TransportAssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.suspend_transport_assignment(
                session,
                _ctx(principal),
                assignment_id,
                request_id=_request_id(request),
            )
    return s.TransportAssignmentResponse.model_validate(row, from_attributes=True)


@router.post(
    "/transport-assignments/{assignment_id}/cancel",
    response_model=s.TransportAssignmentResponse,
    summary="Cancel a transport assignment",
)
async def cancel_transport_assignment(
    assignment_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("transport_assignments:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TransportAssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.cancel_transport_assignment(
                session,
                _ctx(principal),
                assignment_id,
                request_id=_request_id(request),
            )
    return s.TransportAssignmentResponse.model_validate(row, from_attributes=True)


@router.post(
    "/transport-assignments/{assignment_id}/expire",
    response_model=s.TransportAssignmentResponse,
    summary="Expire a transport assignment",
)
async def expire_transport_assignment(
    assignment_id: UUID,
    body: s.TransportAssignmentExpireRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require("transport_assignments:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TransportAssignmentResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.expire_transport_assignment(
                session,
                _ctx(principal),
                assignment_id,
                effective_to=body.effective_to,
                request_id=_request_id(request),
            )
    return s.TransportAssignmentResponse.model_validate(row, from_attributes=True)


@router.get("/trips", response_model=s.TripListResponse, summary="List transport trips")
async def list_trips(
    principal: Annotated[Principal, Depends(require("trips:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    service_date: date | None = None,
    bus_id: UUID | None = None,
    route_id: UUID | None = None,
    attendant_id: UUID | None = None,
    status: str | None = None,
    shift: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> s.TripListResponse:
    _validate_cursor(cursor)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows, next_cursor = await svc.list_trips(
                session,
                _ctx(principal),
                service_date=service_date,
                bus_id=bus_id,
                route_id=route_id,
                attendant_id=attendant_id,
                status=status,
                shift=shift,
                limit=limit,
                cursor=cursor,
            )
    return s.TripListResponse(
        items=[s.TripResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )


@router.post("/trips", response_model=s.TripResponse, summary="Schedule a transport trip")
async def create_trip(
    body: s.TripCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("trips:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TripResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.create_trip(
                session,
                _ctx(principal),
                bus_id=body.bus_id,
                route_id=body.route_id,
                attendant_id=body.attendant_id,
                service_date=body.service_date,
                shift=body.shift,
                request_id=_request_id(request),
            )
    return s.TripResponse.model_validate(row, from_attributes=True)


@router.get("/trips/{trip_id}", response_model=s.TripResponse, summary="Get a transport trip")
async def get_trip(
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require("trips:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TripResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_trip(session, _ctx(principal), trip_id)
    return s.TripResponse.model_validate(row, from_attributes=True)


@router.post("/trips/{trip_id}/start", response_model=s.TripResponse, summary="Start trip boarding")
async def start_trip(
    trip_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("trips:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TripResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.start_trip(session, _ctx(principal), trip_id, request_id=_request_id(request))
    return s.TripResponse.model_validate(row, from_attributes=True)


@router.post("/trips/{trip_id}/begin", response_model=s.TripResponse, summary="Mark trip in progress")
async def begin_trip(
    trip_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("trips:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TripResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.begin_trip_in_progress(
                session,
                _ctx(principal),
                trip_id,
                request_id=_request_id(request),
            )
    return s.TripResponse.model_validate(row, from_attributes=True)


@router.post("/trips/{trip_id}/complete", response_model=s.TripResponse, summary="Complete a trip")
async def complete_trip(
    trip_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("trips:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TripResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.complete_trip(session, _ctx(principal), trip_id, request_id=_request_id(request))
    return s.TripResponse.model_validate(row, from_attributes=True)


@router.post("/trips/{trip_id}/cancel", response_model=s.TripResponse, summary="Cancel a trip")
async def cancel_trip(
    trip_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("trips:write"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TripResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.cancel_trip(session, _ctx(principal), trip_id, request_id=_request_id(request))
    return s.TripResponse.model_validate(row, from_attributes=True)
