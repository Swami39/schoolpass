from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.adapters.redis import Cache
from schoolpass.api.deps import get_session_factory, get_settings_dep
from schoolpass.config import Settings
from schoolpass.errors import ValidationFailed
from schoolpass.rfid import ingest as ingest_svc
from schoolpass.rfid.schemas import RfidEventPayload, RfidIngestAcceptedResponse

router = APIRouter(prefix="/ingest/v1", tags=["rfid-ingest"])


def get_redis(request: Request) -> Cache:
    return cast(Cache, request.app.state.redis)


@router.post("/rfid/events", response_model=RfidIngestAcceptedResponse)
async def post_rfid_event(
    request: Request,
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    redis: Annotated[Cache, Depends(get_redis)],
) -> RfidIngestAcceptedResponse:
    raw = await request.body()
    try:
        payload = RfidEventPayload.model_validate_json(raw)
    except Exception as exc:
        raise ValidationFailed("Invalid event payload", code="invalid_event_payload") from exc
    correlation_id = getattr(request.state, "request_id", None)
    return await ingest_svc.ingest_rfid_event(
        factory,
        settings,
        redis,
        method=request.method,
        path=ingest_svc.ingest_path(),
        body=raw,
        headers=dict(request.headers),
        payload=payload,
        correlation_id=correlation_id,
    )
