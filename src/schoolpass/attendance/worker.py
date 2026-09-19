from __future__ import annotations

from sqlalchemy import select

from schoolpass.attendance.engine import process_pending_observations
from schoolpass.config import get_settings
from schoolpass.db.session import apply_tenant_context, create_engine, session_factory
from schoolpass.identity.models import Tenant
from schoolpass.tenancy.context import TenantContext


async def process_attendance_batch() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url, null_pool=settings.app_env == "test")
    factory = session_factory(engine)
    total = 0
    try:
        async with factory() as session:
            async with session.begin():
                await apply_tenant_context(
                    session,
                    TenantContext(actor_type="system", tenant_id=None, user_id=None),
                )
                tenant_ids = list((await session.execute(select(Tenant.id))).scalars())
        for tenant_id in tenant_ids:
            async with factory() as session:
                async with session.begin():
                    await apply_tenant_context(
                        session,
                        TenantContext(actor_type="worker", tenant_id=tenant_id, user_id=None),
                    )
                    total += await process_pending_observations(session)
    finally:
        await engine.dispose()
    return total
