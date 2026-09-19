from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from uuid import UUID

import pyotp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.adapters.redis import Cache
from schoolpass.audit.service import record_audit
from schoolpass.auth.crypto import decrypt_secret, encrypt_secret
from schoolpass.auth.passwords import verify_password
from schoolpass.auth.refresh import (
    issue_refresh_token,
    revoke_user_refresh_tokens,
)
from schoolpass.auth.tokens import encode_access_token, encode_mfa_token
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import AuthenticationError, AuthorizationError, ValidationFailed
from schoolpass.identity.models import PlatformMembership, Role, TenantMembership, User
from schoolpass.outbox.service import enqueue_outbox
from schoolpass.rbac.catalog import MFA_REQUIRED_ROLES, PLATFORM_ROLES
from schoolpass.tenancy.context import TenantContext


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_token: str | None = None
    enrollment_required: bool = False


async def load_memberships(session: AsyncSession, user_id: UUID) -> list[tuple[TenantMembership, Role]]:
    result = await session.execute(
        select(TenantMembership, Role)
        .join(Role, Role.id == TenantMembership.role_id)
        .where(TenantMembership.user_id == user_id, TenantMembership.status == "active")
    )
    return [(row[0], row[1]) for row in result.all()]


async def load_platform_roles(session: AsyncSession, user_id: UUID) -> list[str]:
    result = await session.execute(
        select(Role.name)
        .join(PlatformMembership, PlatformMembership.role_id == Role.id)
        .where(PlatformMembership.user_id == user_id, PlatformMembership.status == "active")
    )
    return list(result.scalars().all())


def _platform(roles: list[str]) -> bool:
    return any(role in PLATFORM_ROLES for role in roles)


async def issue_session(
    session: AsyncSession,
    settings: Settings,
    user: User,
    *,
    tenant_id: UUID | None,
    roles: list[str],
    device_id: UUID | None,
    request_id: str,
) -> AuthTokens:
    access = encode_access_token(
        settings,
        user_id=user.id,
        tenant_id=tenant_id,
        roles=roles,
        mfa=user.mfa_enabled,
        platform=_platform(roles),
    )
    refresh, _ = await issue_refresh_token(session, settings, user_id=user.id, device_id=device_id)
    ctx = TenantContext(actor_type="user", tenant_id=tenant_id, user_id=user.id)
    await apply_tenant_context(session, ctx)
    await record_audit(
        session,
        ctx,
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
        request_id=request_id,
        metadata={"roles": roles},
    )
    await enqueue_outbox(
        session,
        topic="auth.session_started",
        idempotency_key=f"login:{user.id}:{request_id}",
        tenant_id=tenant_id,
        correlation_id=request_id,
        payload={"user_id": str(user.id)},
    )
    user.last_login_at = user.last_login_at
    return AuthTokens(access_token=access, refresh_token=refresh)


async def password_login(
    session: AsyncSession,
    settings: Settings,
    *,
    identifier: str,
    password: str,
    tenant_id: UUID | None,
    device_id: UUID | None,
    request_id: str,
) -> AuthTokens:
    stmt = select(User).where((User.email == identifier) | (User.phone_e164 == identifier))
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid credentials")
    if user.status != "active":
        raise AuthenticationError("Account is not active")

    pairs = await load_memberships(session, user.id)
    platform_roles = await load_platform_roles(session, user.id)
    if not pairs and not platform_roles:
        raise AuthorizationError("No active memberships")
    roles = [role.name for _, role in pairs] + platform_roles
    selected_tenant = tenant_id
    selected_roles = roles
    if tenant_id is not None:
        matching = [(m, r) for m, r in pairs if m.tenant_id == tenant_id]
        if not matching and not _platform(roles):
            raise AuthorizationError("No membership for tenant")
        selected_roles = [r.name for m, r in matching] or roles
    elif len({m.tenant_id for m, _ in pairs}) == 1:
        selected_tenant = pairs[0][0].tenant_id
        selected_roles = [pairs[0][1].name]

    needs_mfa = user.mfa_enabled or bool(set(selected_roles) & MFA_REQUIRED_ROLES)
    if needs_mfa and not user.mfa_enabled:
        return AuthTokens(
            access_token="",
            refresh_token="",
            enrollment_required=True,
            mfa_token=encode_mfa_token(settings, user.id),
        )
    if user.mfa_enabled:
        return AuthTokens(
            access_token="",
            refresh_token="",
            mfa_required=True,
            mfa_token=encode_mfa_token(settings, user.id),
        )
    return await issue_session(
        session,
        settings,
        user,
        tenant_id=selected_tenant,
        roles=selected_roles,
        device_id=device_id,
        request_id=request_id,
    )


async def complete_mfa(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    code: str,
    tenant_id: UUID | None,
    device_id: UUID | None,
    request_id: str,
) -> AuthTokens:
    if not user.mfa_secret_encrypted:
        raise AuthenticationError("MFA is not configured")
    secret = decrypt_secret(settings, user.mfa_secret_encrypted)
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise AuthenticationError("Invalid MFA code")
    pairs = await load_memberships(session, user.id)
    platform_roles = await load_platform_roles(session, user.id)
    roles = [role.name for _, role in pairs] + platform_roles
    selected = tenant_id
    selected_roles = roles
    if tenant_id:
        selected_roles = [r.name for m, r in pairs if m.tenant_id == tenant_id] or roles
    elif len({m.tenant_id for m, _ in pairs}) == 1:
        selected = pairs[0][0].tenant_id
        selected_roles = [pairs[0][1].name]
    return await issue_session(
        session,
        settings,
        user,
        tenant_id=selected,
        roles=selected_roles,
        device_id=device_id,
        request_id=request_id,
    )


def start_mfa_enrollment(settings: Settings) -> tuple[str, str]:
    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name="schoolpass", issuer_name="SchoolPass")
    return secret, uri


def confirm_mfa_enrollment(settings: Settings, user: User, secret: str, code: str) -> None:
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise ValidationFailed("Invalid MFA code")
    user.mfa_secret_encrypted = encrypt_secret(settings, secret)
    user.mfa_enabled = True


async def hash_and_store_otp(redis: Cache, destination: str, ttl: int) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    await redis.set(f"otp:{destination}", digest, ex=ttl)
    return code


async def verify_stored_otp(redis: Cache, destination: str, code: str) -> bool:
    digest = await redis.get(f"otp:{destination}")
    if digest is None:
        return False
    raw = digest.decode("utf-8") if isinstance(digest, bytes) else str(digest)
    ok = hashlib.sha256(code.encode("utf-8")).hexdigest() == raw
    if ok:
        await redis.delete(f"otp:{destination}")
    return ok


async def logout_user(session: AsyncSession, user_id: UUID) -> None:
    await revoke_user_refresh_tokens(session, user_id)
