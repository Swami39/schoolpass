from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.db.session import apply_tenant_context
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport import schemas as s
from schoolpass.transport import services as svc
from schoolpass.transport.attendant_access import load_active_transport_attendant
from schoolpass.transport.devices import register_transport_attendant_client_device

router = APIRouter(prefix="/api/v1/transport-attendant", tags=["transport-attendant"])


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


@router.post("/client-devices", response_model=s.TransportAttendantClientDeviceResponse)
async def register_client_device(
    body: s.TransportAttendantClientDeviceRegisterRequest,
    principal: Annotated[Principal, Depends(require("transport_nfc:sync"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.TransportAttendantClientDeviceResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            device = await register_transport_attendant_client_device(
                session,
                _ctx(principal),
                device_uuid=body.device_uuid,
            )
    return s.TransportAttendantClientDeviceResponse(client_device_id=device.id)


@router.get("/trips", response_model=s.TripListResponse)
async def list_my_trips(
    principal: Annotated[Principal, Depends(require("trips:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    service_date: date | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> s.TripListResponse:
    async with factory() as session:
        async with session.begin():
            ctx = _ctx(principal)
            await apply_tenant_context(session, ctx)
            attendant = await load_active_transport_attendant(session, ctx)
            rows, next_cursor = await svc.list_trips(
                session,
                ctx,
                service_date=service_date or date.today(),
                bus_id=None,
                route_id=None,
                attendant_id=attendant.id,
                status=status,
                shift=None,
                limit=limit,
                cursor=None,
            )
    return s.TripListResponse(
        items=[s.TripResponse.model_validate(r, from_attributes=True) for r in rows],
        next_cursor=next_cursor,
    )
