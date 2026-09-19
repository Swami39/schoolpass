from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.db.session import apply_tenant_context
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport import nfc_sync as nfc
from schoolpass.transport.schemas import TransportNfcSyncRequest, TransportNfcSyncResponse

router = APIRouter(prefix="/api/v1/transport/nfc", tags=["transport-nfc"])


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


@router.post("/events/sync", response_model=TransportNfcSyncResponse)
async def sync_nfc_event(
    request: Request,
    body: TransportNfcSyncRequest,
    principal: Annotated[Principal, Depends(require("transport_nfc:sync"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> TransportNfcSyncResponse:
    request_id = getattr(request.state, "request_id", None)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            device_id = await nfc.get_client_device_for_request(
                session,
                header_value=request.headers.get(nfc.HEADER_CLIENT_DEVICE),
                user_id=principal.user.id,
            )
            result = await nfc.sync_transport_nfc_event(
                session,
                _ctx(principal),
                client_device_id=device_id,
                client_event_id=body.client_event_id,
                event_type=body.event_type,
                card_uid=body.card_uid,
                occurred_at=body.occurred_at,
                trip_id=body.trip_id,
                trip_stop_id=body.trip_stop_id,
                device_sequence=body.device_sequence,
                request_id=request_id,
            )
    return TransportNfcSyncResponse(
        result=result.category.value,
        client_event_id=result.client_event_id,
        server_event_id=result.server_event_id,
        boarding_record_id=result.boarding_record_id,
        occurred_at=result.occurred_at,
        received_at=result.received_at,
        rejection_code=result.rejection_code,
        device_sequence=result.device_sequence,
    )
