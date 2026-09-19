from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.admin.schemas import SchoolProfileUpdateRequest
from schoolpass.audit.service import record_audit
from schoolpass.errors import NotFoundError, ValidationFailed
from schoolpass.identity.models import Tenant
from schoolpass.people.models import FileMetadata
from schoolpass.tenancy.context import TenantContext


async def get_school_profile(session: AsyncSession, ctx: TenantContext) -> Tenant:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    row = await session.get(Tenant, ctx.tenant_id)
    if row is None:
        raise NotFoundError()
    return row


async def _validate_logo_file(session: AsyncSession, ctx: TenantContext, logo_file_id: UUID | None) -> None:
    if logo_file_id is None:
        return
    file_row = await session.get(FileMetadata, logo_file_id)
    if file_row is None or file_row.tenant_id != ctx.tenant_id or file_row.status != "active":
        raise ValidationFailed("logo_file_id is not valid for this school")


async def update_school_profile(
    session: AsyncSession,
    ctx: TenantContext,
    payload: SchoolProfileUpdateRequest,
    *,
    request_id: str | None,
) -> Tenant:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    row = await session.get(Tenant, ctx.tenant_id)
    if row is None:
        raise NotFoundError()

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise ValidationFailed("No fields to update")

    if "logo_file_id" in updates:
        await _validate_logo_file(session, ctx, updates["logo_file_id"])

    changed: dict[str, Any] = {}
    for field, value in updates.items():
        if getattr(row, field) != value:
            changed[field] = value
            setattr(row, field, value)

    if not changed:
        return row

    await session.flush()
    await record_audit(
        session,
        ctx,
        action="tenant.profile.updated",
        resource_type="tenant",
        resource_id=row.id,
        request_id=request_id,
        metadata={"fields": sorted(changed.keys())},
    )
    return row
