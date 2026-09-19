from sqlalchemy import select

from schoolpass.audit.service import record_audit
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import AuditLog, OutboxEvent
from schoolpass.outbox.service import enqueue_outbox
from schoolpass.tenancy.context import TenantContext
from schoolpass.worker.main import publish_outbox_batch


async def test_outbox_written_in_same_transaction(db_factory, world) -> None:
    async with db_factory() as session:
        async with session.begin():
            ctx = TenantContext(actor_type="user", tenant_id=world["tenant_a"], user_id=world["user_a"])
            await apply_tenant_context(session, ctx)
            event = await enqueue_outbox(
                session,
                topic="test.ping",
                idempotency_key=f"ping-{world['user_a']}",
                tenant_id=world["tenant_a"],
                correlation_id="corr-1",
                payload={"user_id": str(world["user_a"])},
            )
            await record_audit(
                session,
                ctx,
                action="test.ping",
                resource_type="outbox",
                resource_id=event.id,
                request_id="corr-1",
            )
            assert event.published_at is None
    assert await publish_outbox_batch() >= 1
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(
                    actor_type="user",
                    tenant_id=world["tenant_a"],
                    user_id=world["user_a"],
                ),
            )
            row = (await session.execute(select(OutboxEvent).where(OutboxEvent.id == event.id))).scalar_one()
            assert row.published_at is not None
            audit = (await session.execute(select(AuditLog).where(AuditLog.resource_id == event.id))).scalar_one()
            assert audit.action == "test.ping"
            assert "password" not in audit.metadata_
