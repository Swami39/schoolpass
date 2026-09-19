from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.adapters.otp import DevOtpStore, ProductionOtpSender
from schoolpass.api.deps import Principal, get_principal, get_session_factory, get_settings_dep
from schoolpass.auth.refresh import rotate_refresh_token
from schoolpass.auth.service import (
    complete_mfa,
    confirm_mfa_enrollment,
    hash_and_store_otp,
    issue_session,
    load_memberships,
    logout_user,
    password_login,
    start_mfa_enrollment,
    verify_stored_otp,
)
from schoolpass.auth.tokens import decode_token, encode_access_token
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import AuthenticationError, AuthorizationError
from schoolpass.identity.models import Role, TenantMembership, User
from schoolpass.rbac.catalog import PLATFORM_ROLES
from schoolpass.tenancy.context import TenantContext

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class PasswordLoginRequest(BaseModel):
    identifier: str
    password: str
    tenant_id: UUID | None = None
    device_id: UUID | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MfaChallengeResponse(BaseModel):
    mfa_required: bool = False
    enrollment_required: bool = False
    mfa_token: str


class RefreshRequest(BaseModel):
    refresh_token: str
    device_id: UUID | None = None


class OtpStartRequest(BaseModel):
    destination: str = Field(min_length=5, max_length=64)


class OtpVerifyRequest(BaseModel):
    destination: str
    code: str = Field(min_length=6, max_length=8)
    tenant_id: UUID | None = None
    device_id: UUID | None = None


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str
    tenant_id: UUID | None = None
    device_id: UUID | None = None


class MfaEnrollStartResponse(BaseModel):
    secret: str
    otpauth_uri: str


class MfaEnrollVerifyRequest(BaseModel):
    mfa_token: str
    secret: str
    code: str


class SelectTenantRequest(BaseModel):
    tenant_id: UUID


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


@router.post("/password/login")
async def login(
    body: PasswordLoginRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> dict[str, Any]:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="system", tenant_id=None, user_id=None))
            result = await session.execute(
                select(User).where((User.email == body.identifier) | (User.phone_e164 == body.identifier))
            )
            user = result.scalar_one_or_none()
            if user is None:
                raise AuthenticationError("Invalid credentials")
            await apply_tenant_context(session, TenantContext(actor_type="user", user_id=user.id, tenant_id=None))
            tokens = await password_login(
                session,
                settings,
                identifier=body.identifier,
                password=body.password,
                tenant_id=body.tenant_id,
                device_id=body.device_id,
                request_id=_request_id(request),
            )
    if tokens.mfa_required or tokens.enrollment_required:
        return MfaChallengeResponse(
            mfa_required=tokens.mfa_required,
            enrollment_required=tokens.enrollment_required,
            mfa_token=tokens.mfa_token or "",
        ).model_dump()
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token).model_dump()


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> TokenResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="system", tenant_id=None, user_id=None))
            raw, row = await rotate_refresh_token(session, settings, body.refresh_token, device_id=body.device_id)
            user = await session.get(User, row.user_id)
            if user is None:
                raise AuthenticationError()
            await apply_tenant_context(session, TenantContext(actor_type="user", user_id=user.id, tenant_id=None))
            memberships = await session.execute(
                select(TenantMembership, Role)
                .join(Role, Role.id == TenantMembership.role_id)
                .where(TenantMembership.user_id == user.id, TenantMembership.status == "active")
            )
            pairs = list(memberships.all())
            roles = [r.name for _, r in pairs]
            tenant_id = pairs[0][0].tenant_id if len({m.tenant_id for m, _ in pairs}) == 1 else None
            access = encode_access_token(
                settings,
                user_id=user.id,
                tenant_id=tenant_id,
                roles=roles,
                mfa=user.mfa_enabled,
                platform=any(name in PLATFORM_ROLES for name in roles),
            )
    return TokenResponse(access_token=access, refresh_token=raw)


@router.post("/logout")
async def logout(
    principal: Annotated[Principal, Depends(get_principal)],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> dict[str, Any]:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, principal.context)
            await logout_user(session, principal.user.id)
    return {"ok": True}


@router.post("/otp/start")
async def otp_start(
    body: OtpStartRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> dict[str, Any]:
    redis = request.app.state.redis
    current = await redis.incr(f"otp:rate:{body.destination}")
    if current == 1:
        await redis.expire(f"otp:rate:{body.destination}", 15 * 60)
    if current > 5:
        raise AuthenticationError("Too many OTP requests")
    code = await hash_and_store_otp(redis, body.destination, settings.otp_ttl_seconds)
    if settings.app_env in {"local", "test"} and settings.otp_dev_allow:
        await DevOtpStore(redis, allow=True).send(body.destination, code)
    else:
        await ProductionOtpSender().send(body.destination, code)
    return {"ok": True}


@router.post("/otp/verify")
async def otp_verify(
    body: OtpVerifyRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> dict[str, Any]:
    redis = request.app.state.redis
    if not await verify_stored_otp(redis, body.destination, body.code):
        raise AuthenticationError("Invalid OTP")
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="system", tenant_id=None, user_id=None))
            result = await session.execute(
                select(User).where((User.email == body.destination) | (User.phone_e164 == body.destination))
            )
            user = result.scalar_one_or_none()
            if user is None:
                raise AuthenticationError("Invalid OTP")
            await apply_tenant_context(session, TenantContext(actor_type="user", user_id=user.id, tenant_id=None))
            pairs = await load_memberships(session, user.id)
            roles = [r.name for _, r in pairs]
            tenant_id = body.tenant_id
            if tenant_id is None and len({m.tenant_id for m, _ in pairs}) == 1:
                tenant_id = pairs[0][0].tenant_id
            tokens = await issue_session(
                session,
                settings,
                user,
                tenant_id=tenant_id,
                roles=roles,
                device_id=body.device_id,
                request_id=_request_id(request),
            )
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token).model_dump()


@router.post("/mfa/verify")
async def mfa_verify(
    body: MfaVerifyRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> dict[str, Any]:
    claims = decode_token(settings, body.mfa_token)
    if claims.get("typ") != "mfa":
        raise AuthenticationError("Invalid token type")
    async with factory() as session:
        async with session.begin():
            user = await session.get(User, UUID(claims["sub"]))
            if user is None:
                raise AuthenticationError()
            await apply_tenant_context(session, TenantContext(actor_type="user", user_id=user.id, tenant_id=None))
            tokens = await complete_mfa(
                session,
                settings,
                user=user,
                code=body.code,
                tenant_id=body.tenant_id,
                device_id=body.device_id,
                request_id=_request_id(request),
            )
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token).model_dump()


@router.post("/mfa/enroll/start", response_model=MfaEnrollStartResponse)
async def mfa_enroll_start(
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> MfaEnrollStartResponse:
    secret, uri = start_mfa_enrollment(settings)
    return MfaEnrollStartResponse(secret=secret, otpauth_uri=uri)


@router.post("/mfa/enroll/verify")
async def mfa_enroll_verify(
    body: MfaEnrollVerifyRequest,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> dict[str, Any]:
    claims = decode_token(settings, body.mfa_token)
    if claims.get("typ") != "mfa":
        raise AuthenticationError("Invalid token type")
    async with factory() as session:
        async with session.begin():
            user = await session.get(User, UUID(claims["sub"]))
            if user is None:
                raise AuthenticationError()
            confirm_mfa_enrollment(settings, user, body.secret, body.code)
    return {"ok": True}


@router.post("/select-tenant", response_model=AccessTokenResponse)
async def select_tenant(
    body: SelectTenantRequest,
    principal: Annotated[Principal, Depends(get_principal)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AccessTokenResponse:
    async with factory() as session:
        async with session.begin():
            ctx = TenantContext(actor_type="user", user_id=principal.user.id, tenant_id=body.tenant_id)
            await apply_tenant_context(session, ctx)
            result = await session.execute(
                select(TenantMembership, Role)
                .join(Role, Role.id == TenantMembership.role_id)
                .where(
                    TenantMembership.user_id == principal.user.id,
                    TenantMembership.tenant_id == body.tenant_id,
                    TenantMembership.status == "active",
                )
            )
            row = result.first()
            if row is None:
                raise AuthorizationError("No membership for tenant")
            access = encode_access_token(
                settings,
                user_id=principal.user.id,
                tenant_id=body.tenant_id,
                roles=[row[1].name],
                mfa=principal.user.mfa_enabled,
                platform=False,
            )
    return AccessTokenResponse(access_token=access)
