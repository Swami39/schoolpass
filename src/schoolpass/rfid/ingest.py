from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.adapters.redis import Cache
from schoolpass.cards.normalize import normalize_hf_uid, normalize_uhf_epc, normalize_uhf_tid
from schoolpass.config import Settings
from schoolpass.db.mixins import utcnow
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import AuthenticationError, AuthorizationError, ConflictError, NotFoundError, RateLimitError
from schoolpass.observability.metrics import metrics
from schoolpass.rfid.models import (
    RfidDevice,
    RfidEvent,
    RfidEventProcessing,
    RfidIngestReject,
    RfidObservation,
    RfidReader,
)
from schoolpass.rfid.resolution import RESOLUTION_INVALID, CardResolution, resolve_card
from schoolpass.rfid.schemas import RfidEventPayload, RfidIngestAcceptedResponse
from schoolpass.rfid.security import (
    INGEST_PATH,
    body_sha256_hex,
    canonical_message,
    parse_request_timestamp,
    verify_signature,
)
from schoolpass.rfid.services import load_device_secret
from schoolpass.tenancy.context import TenantContext

HEADER_DEVICE = "x-device-id"
HEADER_KEY_VERSION = "x-key-version"
HEADER_TIMESTAMP = "x-timestamp"
HEADER_NONCE = "x-nonce"
HEADER_SIGNATURE = "x-signature"


async def record_reject(
    session: AsyncSession,
    *,
    reason_code: str,
    tenant_id: UUID | None = None,
    device_external_id: str | None = None,
    reader_id: UUID | None = None,
    correlation_id: str | None = None,
) -> None:
    await apply_tenant_context(
        session,
        TenantContext(actor_type="system", tenant_id=tenant_id, user_id=None),
    )
    session.add(
        RfidIngestReject(
            tenant_id=tenant_id,
            device_external_id=device_external_id,
            reader_id=reader_id,
            reason_code=reason_code,
            correlation_id=correlation_id,
            created_at=utcnow(),
        )
    )
    await session.flush()
    metrics.increment("rfid_ingest_rejected_total", reason=reason_code)


async def lookup_device(session: AsyncSession, device_external_id: str) -> RfidDevice | None:
    result = await session.execute(select(RfidDevice).where(RfidDevice.device_id == device_external_id))
    return result.scalar_one_or_none()


async def consume_nonce(redis: Cache, *, device_external_id: str, nonce: str, ttl: int) -> bool:
    key = f"rfid:nonce:{device_external_id}:{nonce}"
    ok = await redis.set_nx(key, "1", ex=ttl)
    if not ok:
        metrics.increment("rfid_ingest_replays_total")
    return ok


async def check_rate_limit(redis: Cache, *, device_external_id: str, limit: int) -> bool:
    if limit <= 0:
        return True
    minute = datetime.now(tz=UTC).strftime("%Y%m%d%H%M")
    key = f"rfid:rate:{device_external_id}:{minute}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 70)
    return count <= limit


async def authenticate_ingest(
    session: AsyncSession,
    settings: Settings,
    redis: Cache,
    *,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    correlation_id: str | None,
) -> tuple[RfidDevice, RfidReader, int]:
    device_external_id = headers.get(HEADER_DEVICE, "").strip()
    key_version_raw = headers.get(HEADER_KEY_VERSION, "").strip()
    timestamp_raw = headers.get(HEADER_TIMESTAMP, "").strip()
    nonce = headers.get(HEADER_NONCE, "").strip()
    signature = headers.get(HEADER_SIGNATURE, "").strip()

    if not all([device_external_id, key_version_raw, timestamp_raw, nonce, signature]):
        await record_reject(
            session,
            reason_code="invalid_device_auth",
            device_external_id=device_external_id or None,
            correlation_id=correlation_id,
        )
        raise AuthenticationError("Missing ingest authentication headers", code="invalid_device_auth")

    try:
        key_version = int(key_version_raw)
    except ValueError as exc:
        await record_reject(
            session,
            reason_code="unknown_key_version",
            device_external_id=device_external_id,
            correlation_id=correlation_id,
        )
        raise AuthenticationError("Invalid key version", code="unknown_key_version") from exc

    try:
        parse_request_timestamp(timestamp_raw, max_skew_seconds=settings.rfid_request_max_skew_seconds)
    except ValueError as exc:
        code = str(exc)
        await record_reject(
            session,
            reason_code=code,
            device_external_id=device_external_id,
            correlation_id=correlation_id,
        )
        raise AuthenticationError("Request timestamp rejected", code=code) from exc

    device = await lookup_device(session, device_external_id)
    if device is None:
        await record_reject(
            session,
            reason_code="unknown_device",
            device_external_id=device_external_id,
            correlation_id=correlation_id,
        )
        raise AuthenticationError("Unknown device", code="invalid_device_auth")

    if device.status == "blocked":
        await record_reject(
            session,
            reason_code="device_blocked",
            tenant_id=device.tenant_id,
            device_external_id=device_external_id,
            correlation_id=correlation_id,
        )
        raise AuthorizationError("Device blocked", code="device_blocked")

    if device.status == "retired":
        await record_reject(
            session,
            reason_code="device_retired",
            tenant_id=device.tenant_id,
            device_external_id=device_external_id,
            correlation_id=correlation_id,
        )
        raise AuthorizationError("Device retired", code="device_retired")

    secret = await load_device_secret(session, settings, device.id, key_version)
    if secret is None:
        await record_reject(
            session,
            reason_code="unknown_key_version",
            tenant_id=device.tenant_id,
            device_external_id=device_external_id,
            correlation_id=correlation_id,
        )
        raise AuthenticationError("Unknown key version", code="unknown_key_version")

    body_hash = body_sha256_hex(body)
    message = canonical_message(
        method=method,
        path=path,
        timestamp=timestamp_raw,
        nonce=nonce,
        body_hash=body_hash,
        device_id=device_external_id,
        key_version=str(key_version),
    )
    if not verify_signature(secret, message, signature):
        metrics.increment("rfid_ingest_signature_failures_total")
        await record_reject(
            session,
            reason_code="invalid_signature",
            tenant_id=device.tenant_id,
            device_external_id=device_external_id,
            correlation_id=correlation_id,
        )
        raise AuthenticationError("Invalid signature", code="invalid_signature")

    if not await check_rate_limit(
        redis,
        device_external_id=device_external_id,
        limit=settings.rfid_ingest_rate_limit_per_minute,
    ):
        raise RateLimitError("Ingest rate limit exceeded")

    if not await consume_nonce(
        redis,
        device_external_id=device_external_id,
        nonce=nonce,
        ttl=settings.rfid_nonce_ttl_seconds,
    ):
        await record_reject(
            session,
            reason_code="replayed_nonce",
            tenant_id=device.tenant_id,
            device_external_id=device_external_id,
            correlation_id=correlation_id,
        )
        raise ConflictError("Replayed request", code="replayed_request")

    await apply_tenant_context(
        session,
        TenantContext(actor_type="device", tenant_id=device.tenant_id, user_id=None),
    )
    reader = await session.get(RfidReader, device.reader_id)
    if reader is None or reader.tenant_id != device.tenant_id:
        await record_reject(
            session,
            reason_code="unknown_reader",
            tenant_id=device.tenant_id,
            device_external_id=device_external_id,
            reader_id=device.reader_id,
            correlation_id=correlation_id,
        )
        raise NotFoundError("Unknown reader", code="unknown_reader")

    if reader.status == "blocked":
        await record_reject(
            session,
            reason_code="reader_blocked",
            tenant_id=device.tenant_id,
            device_external_id=device_external_id,
            reader_id=reader.id,
            correlation_id=correlation_id,
        )
        raise AuthorizationError("Reader blocked", code="device_blocked")

    if reader.status == "retired":
        await record_reject(
            session,
            reason_code="reader_retired",
            tenant_id=device.tenant_id,
            device_external_id=device_external_id,
            reader_id=reader.id,
            correlation_id=correlation_id,
        )
        raise AuthorizationError("Reader retired", code="device_retired")

    return device, reader, key_version


async def find_existing_event(
    session: AsyncSession,
    tenant_id: UUID,
    reader_id: UUID,
    device_event_id: str,
) -> RfidEvent | None:
    result = await session.execute(
        select(RfidEvent).where(
            RfidEvent.tenant_id == tenant_id,
            RfidEvent.reader_id == reader_id,
            RfidEvent.device_event_id == device_event_id,
        )
    )
    return result.scalar_one_or_none()


async def observation_for_event(session: AsyncSession, event_id: UUID) -> RfidObservation | None:
    result = await session.execute(select(RfidObservation).where(RfidObservation.rfid_event_id == event_id))
    return result.scalar_one_or_none()


async def process_event_payload(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    reader: RfidReader,
    device: RfidDevice,
    payload: RfidEventPayload,
    key_version: int,
    received_at: datetime,
) -> tuple[RfidEvent, RfidObservation | None, bool]:
    existing = await find_existing_event(session, tenant_id, reader.id, payload.device_event_id)
    if existing is not None:
        obs = await observation_for_event(session, existing.id)
        metrics.increment("rfid_ingest_duplicates_total")
        return existing, obs, True

    hf = normalize_hf_uid(payload.hf_uid)
    epc = normalize_uhf_epc(payload.uhf_epc)
    tid = normalize_uhf_tid(payload.uhf_tid)
    if not hf and not epc and not tid:
        resolution = CardResolution(resolution_status=RESOLUTION_INVALID)
    else:
        resolution = await resolve_card(
            session,
            tenant_id,
            hf_uid=hf,
            uhf_epc=epc,
            uhf_tid=tid,
            occurred_at=payload.occurred_at,
        )

    event = RfidEvent(
        tenant_id=tenant_id,
        reader_id=reader.id,
        device_uuid=device.id,
        device_event_id=payload.device_event_id,
        physical_card_id=resolution.physical_card_id,
        assignment_id=resolution.assignment_id,
        student_id=resolution.student_id,
        hf_uid=hf,
        uhf_epc=epc,
        uhf_tid=tid,
        antenna=payload.antenna,
        rssi=Decimal(str(payload.rssi)) if payload.rssi is not None else None,
        direction=payload.direction,
        occurred_at=payload.occurred_at,
        received_at=received_at,
        signature_key_version=key_version,
        ingest_status="accepted",
        created_at=utcnow(),
    )
    session.add(event)
    try:
        await session.flush()
    except IntegrityError:
        raise

    processing = RfidEventProcessing(
        tenant_id=tenant_id,
        rfid_event_id=event.id,
        status="processing",
        attempt_count=1,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(processing)

    observation = RfidObservation(
        tenant_id=tenant_id,
        rfid_event_id=event.id,
        physical_card_id=resolution.physical_card_id,
        assignment_id=resolution.assignment_id,
        student_id=resolution.student_id,
        resolution_status=resolution.resolution_status,
        observed_at=payload.occurred_at,
        created_at=utcnow(),
    )
    session.add(observation)

    processing.status = "processed"
    processing.processed_at = utcnow()
    processing.updated_at = utcnow()
    device.last_seen_at = received_at
    device.updated_at = utcnow()
    await session.flush()
    metrics.increment("rfid_event_resolution_total", result=resolution.resolution_status)
    return event, observation, False


async def ingest_rfid_event(
    factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    redis: Cache,
    *,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    payload: RfidEventPayload,
    correlation_id: str | None,
) -> RfidIngestAcceptedResponse:
    metrics.increment("rfid_ingest_requests_total")
    received_at = utcnow()
    auth_headers = {k.lower(): v for k, v in headers.items()}

    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="system", tenant_id=None, user_id=None))
            device, reader, key_version = await authenticate_ingest(
                session,
                settings,
                redis,
                method=method,
                path=path,
                body=body,
                headers=auth_headers,
                correlation_id=correlation_id,
            )

    ctx = TenantContext(actor_type="device", tenant_id=device.tenant_id, user_id=None)
    observation: RfidObservation | None = None
    duplicate = False
    event: RfidEvent
    try:
        async with factory() as session:
            async with session.begin():
                await apply_tenant_context(session, ctx)
                event, observation, duplicate = await process_event_payload(
                    session,
                    tenant_id=device.tenant_id,
                    reader=reader,
                    device=device,
                    payload=payload,
                    key_version=key_version,
                    received_at=received_at,
                )
    except IntegrityError:
        async with factory() as session:
            async with session.begin():
                await apply_tenant_context(session, ctx)
                existing = await find_existing_event(
                    session,
                    device.tenant_id,
                    reader.id,
                    payload.device_event_id,
                )
                if existing is None:
                    raise
                observation = await observation_for_event(session, existing.id)
                event = existing
                duplicate = True
                metrics.increment("rfid_ingest_duplicates_total")

    return RfidIngestAcceptedResponse(
        duplicate=duplicate,
        event_id=event.id,
        resolution_status=observation.resolution_status if observation else None,
    )


def ingest_path() -> str:
    return INGEST_PATH
