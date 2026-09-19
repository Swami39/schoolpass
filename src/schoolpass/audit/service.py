from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.identity.models import AuditLog
from schoolpass.tenancy.context import TenantContext


async def record_audit(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    request_id: str | None,
    metadata: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.user_id,
            actor_type=ctx.actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_=metadata or {},
            request_id=request_id,
            ip=ip,
        )
    )
