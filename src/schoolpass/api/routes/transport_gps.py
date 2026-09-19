from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.adapters.redis import Cache
from schoolpass.api.deps import Principal, get_session_factory, require
from schoolpass.api.routes.rfid_ingest import get_redis
from schoolpass.db.session import apply_tenant_context
from schoolpass.observability.logging import get_logger
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport import gps_sync as gps
from schoolpass.transport.gps_redis import TripLastLocation, try_update_trip_last_location
from schoolpass.transport.models import LocationSample
from schoolpass.transport.schemas import (
    LocationSampleListResponse,
    LocationSampleResponse,
    TransportGpsBatchSyncRequest,
    TransportGpsBatchSyncResponse,
    TransportGpsSampleSyncResult,
)

log = get_logger("schoolpass.transport.gps_api")

router = APIRouter(prefix="/api/v1/transport/gps", tags=["transport-gps"])


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


@router.post("/samples/sync", response_model=TransportGpsBatchSyncResponse)
async def sync_gps_samples(
    request: Request,
    body: TransportGpsBatchSyncRequest,
    principal: Annotated[Principal, Depends(require("gps_samples:sync"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    redis: Annotated[Cache, Depends(get_redis)],
) -> TransportGpsBatchSyncResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            device_id = await gps.get_client_device_for_request(
                session,
                header_value=request.headers.get(gps.HEADER_CLIENT_DEVICE),
                user_id=principal.user.id,
            )
            inputs = [
                gps.GpsSampleInput(
                    client_sample_id=item.client_sample_id,
                    trip_id=item.trip_id,
                    latitude=item.latitude,
                    longitude=item.longitude,
                    occurred_at=item.occurred_at,
                    bus_id=item.bus_id,
                    accuracy_meters=item.accuracy_meters,
                    altitude_meters=item.altitude_meters,
                    speed_mps=item.speed_mps,
                    heading_degrees=item.heading_degrees,
                    device_sequence=item.device_sequence,
                    source=item.source,
                )
                for item in body.samples
            ]
            results = await gps.sync_transport_gps_batch(
                session,
                _ctx(principal),
                client_device_id=device_id,
                samples=inputs,
            )

    for result in results:
        if result.category != gps.GpsSyncResultCategory.PROCESSED or not result.cache_latest:
            continue
        if (
            result.trip_id is not None
            and result.bus_id is not None
            and result.latitude is not None
            and result.longitude is not None
        ):
            try:
                await try_update_trip_last_location(
                    redis,
                    TripLastLocation(
                        trip_id=result.trip_id,
                        bus_id=result.bus_id,
                        latitude=result.latitude,
                        longitude=result.longitude,
                        occurred_at=result.occurred_at,
                        accuracy_meters=result.accuracy_meters,
                        received_at=result.received_at,
                    ),
                )
            except Exception:
                log.warning("gps_redis_update_failed", trip_id=str(result.trip_id))

    return TransportGpsBatchSyncResponse(
        results=[
            TransportGpsSampleSyncResult(
                result=r.category.value,
                client_sample_id=r.client_sample_id,
                server_sample_id=r.server_sample_id,
                occurred_at=r.occurred_at,
                received_at=r.received_at,
                rejection_code=r.rejection_code,
                device_sequence=r.device_sequence,
            )
            for r in results
        ]
    )


@router.get("/trips/{trip_id}/samples", response_model=LocationSampleListResponse)
async def list_trip_gps_samples(
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require("gps_samples:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    limit: int = 100,
) -> LocationSampleListResponse:
    if limit < 1 or limit > 500:
        limit = 100
    async with factory() as session:
        await apply_tenant_context(session, _ctx(principal))
        rows = (
            await session.execute(
                select(LocationSample)
                .where(
                    LocationSample.trip_id == trip_id,
                    LocationSample.processing_state == gps.PROCESSING_RECORDED,
                )
                .order_by(LocationSample.occurred_at.desc())
                .limit(limit)
            )
        ).scalars()
        items = [
            LocationSampleResponse(
                id=row.id,
                trip_id=row.trip_id,
                bus_id=row.bus_id,
                latitude=row.latitude,
                longitude=row.longitude,
                accuracy_meters=row.accuracy_meters,
                occurred_at=row.occurred_at,
                received_at=row.received_at,
                source=row.source,
            )
            for row in rows
        ]
    return LocationSampleListResponse(items=items)
