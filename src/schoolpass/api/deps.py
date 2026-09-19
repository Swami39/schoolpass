from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.auth.tokens import decode_token
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.errors import AuthenticationError, AuthorizationError
from schoolpass.identity.models import Role, TenantMembership, User
from schoolpass.rbac.catalog import PLATFORM_ROLES, ROLE_PERMISSIONS
from schoolpass.tenancy.context import TenantContext


class Principal:
    def __init__(self, user: User, roles: list[str], tenant_id: UUID | None, claims: dict[str, Any]) -> None:
        self.user = user
        self.roles = roles
        self.tenant_id = tenant_id
        self.claims = claims
        self.permissions: set[str] = set()

    @property
    def context(self) -> TenantContext:
        if any(role in PLATFORM_ROLES for role in self.roles) and self.tenant_id is None:
            return TenantContext(actor_type="platform", user_id=self.user.id, tenant_id=None)
        return TenantContext(actor_type="user", user_id=self.user.id, tenant_id=self.tenant_id)


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return factory


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise AuthenticationError()
    return header.split(" ", 1)[1].strip()


async def get_principal(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> Principal:
    claims = decode_token(settings, bearer_token(request))
    if claims.get("typ") != "access":
        raise AuthenticationError("Invalid token type")
    user_id = UUID(claims["sub"])
    tenant_id = UUID(claims["tid"]) if claims.get("tid") else None
    ctx = TenantContext(
        actor_type="platform" if claims.get("plat") and tenant_id is None else "user",
        user_id=user_id,
        tenant_id=tenant_id,
    )
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, ctx)
            user = await session.get(User, user_id)
            if user is None or user.status != "active":
                raise AuthenticationError("Invalid session")
            roles: list[str] = list(claims.get("roles") or [])
            if tenant_id is not None:
                result = await session.execute(
                    select(TenantMembership, Role)
                    .join(Role, Role.id == TenantMembership.role_id)
                    .where(
                        TenantMembership.user_id == user_id,
                        TenantMembership.tenant_id == tenant_id,
                        TenantMembership.status == "active",
                    )
                )
                row = result.first()
                if row is None and not claims.get("plat"):
                    raise AuthorizationError("Membership is not valid for this tenant")
                if row is not None:
                    roles = [row[1].name]
            principal = Principal(user, roles, tenant_id, claims)
            request.state.principal = principal
            request.state.tenant_context = ctx
            return principal


def require(*permissions: str) -> Callable[..., Any]:
    async def _inner(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        allowed: set[str] = set()
        for role in principal.roles:
            allowed.update(ROLE_PERMISSIONS.get(role, ()))
        principal.permissions = allowed
        if permissions and not set(permissions).issubset(allowed):
            raise AuthorizationError()
        tenant_scoped = any(
            p.startswith(
                (
                    "tenant:",
                    "staff:",
                    "membership:",
                    "audit:",
                    "students:",
                    "guardians:",
                    "enrollments:",
                    "student_guardians:",
                    "academic:",
                    "files:",
                    "cards:",
                    "card_assignments:",
                    "rfid_readers:",
                    "rfid_devices:",
                    "rfid_events:",
                    "attendance:",
                    "buses:",
                    "routes:",
                    "route_stops:",
                    "transport_assignments:",
                    "transport_attendants:",
                    "trips:",
                    "transport_nfc:",
                    "transport_boarding:",
                    "gps_samples:",
                    "parent:",
                    "teacher:",
                )
            )
            for p in permissions
        )
        if tenant_scoped and principal.tenant_id is None and not principal.claims.get("plat"):
            raise AuthorizationError("Tenant membership is required")
        return principal

    return _inner
