from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from schoolpass.adapters.redis import RedisCache
from schoolpass.adapters.service_bus import AzureServiceBus, LocalRedisBus
from schoolpass.attendance.worker import process_attendance_batch
from schoolpass.config import get_settings
from schoolpass.db.session import apply_tenant_context, create_engine, session_factory
from schoolpass.identity.models import OutboxEvent
from schoolpass.observability.logging import configure_logging, get_logger
from schoolpass.tenancy.context import TenantContext

log = get_logger("schoolpass.worker")


async def publish_outbox_batch() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url, null_pool=settings.app_env == "test")
    factory = session_factory(engine)
    redis = RedisCache(settings.redis_url)
    bus = (
        AzureServiceBus(settings.azure_service_bus_fully_qualified_namespace)
        if settings.service_bus_mode == "azure"
        else LocalRedisBus(redis)
    )
    published = 0
    try:
        async with factory() as session:
            async with session.begin():
                await apply_tenant_context(session, TenantContext(actor_type="system", tenant_id=None, user_id=None))
                result = await session.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.published_at.is_(None))
                    .order_by(OutboxEvent.created_at)
                    .limit(50)
                    .with_for_update(skip_locked=True)
                )
                rows = list(result.scalars())
                for row in rows:
                    if row.tenant_id is not None:
                        await apply_tenant_context(
                            session,
                            TenantContext(
                                actor_type="worker",
                                tenant_id=row.tenant_id,
                                user_id=None,
                            ),
                        )
                    try:
                        await bus.publish(
                            row.topic,
                            {
                                "id": str(row.id),
                                "tenant_id": str(row.tenant_id) if row.tenant_id else None,
                                "idempotency_key": row.idempotency_key,
                                "schema_version": row.schema_version,
                                "payload": row.payload,
                            },
                        )
                        row.published_at = datetime.now(UTC)
                        row.attempts += 1
                        published += 1
                    except Exception as exc:  # noqa: BLE001
                        row.attempts += 1
                        row.last_error = type(exc).__name__
                        log.error("outbox_publish_failed", outbox_id=str(row.id), error=type(exc).__name__)
                    await apply_tenant_context(
                        session, TenantContext(actor_type="system", tenant_id=None, user_id=None)
                    )
    finally:
        await redis.close()
        await engine.dispose()
    return published


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info("worker_started", env=settings.app_env)
    while True:
        outbox = await publish_outbox_batch()
        attendance = await process_attendance_batch()
        await asyncio.sleep(1 if outbox or attendance else 5)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
