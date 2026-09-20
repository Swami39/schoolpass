"""Provision parent/teacher login accounts for directory records."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.auth.passwords import hash_password
from schoolpass.config import get_settings
from schoolpass.errors import ValidationFailed
from schoolpass.identity.models import Role, TenantMembership, User
from schoolpass.tenancy.context import TenantContext


def _tenant_id(ctx: TenantContext) -> UUID:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    return ctx.tenant_id


async def ensure_user_with_role(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    email: str,
    role_name: str,
    phone_e164: str | None = None,
) -> User:
    """Find or create a user and grant the tenant role. Does not overwrite existing passwords."""
    normalized = email.strip().lower()
    if not normalized:
        raise ValidationFailed("email is required to create a login")
    user = (await session.execute(select(User).where(User.email == normalized))).scalar_one_or_none()
    bootstrap = get_settings().directory_bootstrap_password.strip()
    if user is None:
        user = User(
            email=normalized,
            phone_e164=None,
            password_hash=hash_password(bootstrap) if bootstrap else None,
            status="active",
        )
        session.add(user)
        await session.flush()
    else:
        if user.password_hash is None and bootstrap:
            user.password_hash = hash_password(bootstrap)

    role = (
        await session.execute(select(Role).where(Role.name == role_name, Role.is_system.is_(True)))
    ).scalar_one_or_none()
    if role is None:
        raise ValidationFailed(f"System role '{role_name}' is not configured")
    existing = (
        await session.execute(
            select(TenantMembership).where(
                TenantMembership.tenant_id == _tenant_id(ctx),
                TenantMembership.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            TenantMembership(
                tenant_id=_tenant_id(ctx),
                user_id=user.id,
                role_id=role.id,
                status="active",
            )
        )
        await session.flush()
    return user
