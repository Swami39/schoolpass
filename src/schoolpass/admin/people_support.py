from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.errors import ValidationFailed
from schoolpass.people.models import FileMetadata
from schoolpass.tenancy.context import TenantContext


async def validate_student_photo(
    session: AsyncSession,
    ctx: TenantContext,
    photo_file_id: UUID | None,
) -> None:
    if photo_file_id is None:
        return
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    row = await session.get(FileMetadata, photo_file_id)
    if row is None or row.tenant_id != ctx.tenant_id or row.status != "active":
        raise ValidationFailed("photo_file_id is not valid for this school")
