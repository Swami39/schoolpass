from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.audit.service import record_audit
from schoolpass.errors import ConflictError, NotFoundError, ValidationFailed
from schoolpass.identity.models import Role, StaffProfile, TenantMembership, User
from schoolpass.people.pagination import decode_cursor, encode_cursor
from schoolpass.tenancy.context import TenantContext

ALLOWED_STAFF_TYPES = frozenset({"teacher", "attendant", "bus_attendant", "office", "finance"})
STAFF_TYPE_ROLE: dict[str, str] = {
    "teacher": "teacher",
    "attendant": "bus_attendant",
    "bus_attendant": "bus_attendant",
}

MAX_PAGE_SIZE = 200


def _tenant_id(ctx: TenantContext) -> UUID:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    return ctx.tenant_id


async def _audit(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    action: str,
    resource_id: UUID,
    request_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await record_audit(
        session,
        ctx,
        action=action,
        resource_type="staff_profile",
        resource_id=resource_id,
        request_id=request_id,
        metadata=metadata or {},
    )


async def get_staff(session: AsyncSession, ctx: TenantContext, staff_id: UUID) -> StaffProfile:
    row = await session.get(StaffProfile, staff_id)
    if row is None or row.tenant_id != _tenant_id(ctx):
        raise NotFoundError()
    return row


async def list_staff(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    staff_type: str | None,
    search: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[tuple[StaffProfile, User | None]], str | None]:
    tenant_id = _tenant_id(ctx)
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    stmt = (
        select(StaffProfile, User)
        .join(User, User.id == StaffProfile.user_id)
        .where(StaffProfile.tenant_id == tenant_id)
        .order_by(StaffProfile.created_at.desc(), StaffProfile.id.desc())
    )
    if staff_type:
        stmt = stmt.where(StaffProfile.staff_type == staff_type)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                User.email.ilike(pattern),
                StaffProfile.employee_code.ilike(pattern),
            )
        )
    decoded = decode_cursor(cursor) if cursor else None
    if decoded:
        created_at, row_id = decoded
        stmt = stmt.where(
            or_(
                StaffProfile.created_at < created_at,
                and_(StaffProfile.created_at == created_at, StaffProfile.id < row_id),
            )
        )
    stmt = stmt.limit(limit + 1)
    raw_rows = list((await session.execute(stmt)).all())
    next_cursor = None
    if len(raw_rows) > limit:
        last_staff = raw_rows[limit - 1][0]
        next_cursor = encode_cursor(created_at=last_staff.created_at, row_id=last_staff.id)
        raw_rows = raw_rows[:limit]
    rows = [(staff, user) for staff, user in raw_rows]
    return rows, next_cursor


async def create_staff(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    user_id: UUID,
    staff_type: str,
    employee_code: str | None,
    request_id: str | None,
) -> StaffProfile:
    if staff_type not in ALLOWED_STAFF_TYPES:
        raise ValidationFailed("Invalid staff type for school administration")
    user = await session.get(User, user_id)
    if user is None:
        raise ValidationFailed("User not found")
    row = StaffProfile(
        tenant_id=_tenant_id(ctx),
        user_id=user_id,
        staff_type=staff_type,
        employee_code=employee_code,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Staff profile already exists for this user") from exc

    role_name = STAFF_TYPE_ROLE.get(staff_type)
    if role_name is not None:
        role = (
            await session.execute(select(Role).where(Role.name == role_name, Role.is_system.is_(True)))
        ).scalar_one_or_none()
        if role is not None:
            existing = (
                await session.execute(
                    select(TenantMembership).where(
                        TenantMembership.tenant_id == _tenant_id(ctx),
                        TenantMembership.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    TenantMembership(
                        tenant_id=_tenant_id(ctx),
                        user_id=user_id,
                        role_id=role.id,
                    )
                )
                await session.flush()

    await _audit(session, ctx, action="staff.created", resource_id=row.id, request_id=request_id)
    return row


async def update_staff(
    session: AsyncSession,
    ctx: TenantContext,
    staff_id: UUID,
    *,
    fields: dict[str, Any],
    request_id: str | None,
) -> StaffProfile:
    row = await get_staff(session, ctx, staff_id)
    if not fields:
        raise ValidationFailed("No fields to update")
    if "staff_type" in fields and fields["staff_type"] not in ALLOWED_STAFF_TYPES:
        raise ValidationFailed("Invalid staff type")
    changed: dict[str, Any] = {}
    for key, value in fields.items():
        if hasattr(row, key) and getattr(row, key) != value:
            changed[key] = value
            setattr(row, key, value)
    if not changed:
        return row
    await session.flush()
    await _audit(
        session,
        ctx,
        action="staff.updated",
        resource_id=row.id,
        request_id=request_id,
        metadata={"fields": sorted(changed.keys())},
    )
    return row
